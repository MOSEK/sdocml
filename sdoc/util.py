from UserDict import UserDict
import collections
import zipfile
import tarfile
import tempfile
import os, os.path, stat
import time
import threading



class Position:
    def __init__(self,filename,line):
        self.filename = filename
        self.line = line        
    def __repr__(self):
        return '%s:%d' % (self.filename,self.line)
    def brief(self):
        return '%s:%d' % (os.path.basename(self.filename), self.line)


class MotexException(Exception):
    def __init__(self,msg,trace=None):
        self.msg = msg
        self.trace = trace or []
    def __str__(self):
        return '%s%s' % (self.msg,''.join(['\n\tfrom %s' % t for t in self.trace]))

class BibItemError(Exception):
    pass
class MathError(MotexException):
    pass

class MacroError(MotexException): pass

class MacroArgErrorX(MotexException):
    def __init__(self,msg):
        MotexException.__init__(self,msg)

class MacroArgError(MotexException):
    pass
class NodeError(MotexException):
    pass

class XMLIdError(MotexException):
    pass
class XMLIdRefError(MotexException):
    pass

class XMLError(MotexException):
    pass

class DocumentAssert(MotexException):
    pass

class CondError(MotexException):
    pass

class NodeIncludeError(MotexException):
    pass
    




class CondOpr(str):
    pass

class Cond:
    And = CondOpr('+')
    Or  = CondOpr('|')
    Xor = CondOpr('/')
    Not = CondOpr('!')

class CondTerm(unicode):
    pass

class CondIsDef(unicode):
    pass


class CondExp(list):
    pass

class DfltDict(UserDict):
    def __init__(self,cons=lambda: None):
        UserDict.__init__(self)
        self.__cons = cons
    def __ensurekey(self,k):
        if not self.data.has_key(k):
            self.data[k] = self.__cons()
    def __getitem__(self,k):
        self.__ensurekey(k)
        return self.data[k]


class CommandDict(UserDict):
    def __init__(self,parent=None):
        UserDict.__init__(self)

        assert parent is None or isinstance(parent,CommandDict)
        self.__parent = parent

        self.__lookuptable = {}

    def __getitem__(self,key):
        try:
            return self.data[key]
        except KeyError:
            if self.__parent is not None:
                return self.__parent[key]
            else:
                raise

    def has_key(self,key):
        return self.data.has_key(key) or self.__parent.has_key(key)

    def __setitem__(self,key,value):
        if not self.data.has_key(key):
            self.data[key] = value
        else:
            raise KeyError('Macro "%s" already defined' % key)

    def dictLookup(self,key):
        if self.__lookuptable.has_key(key):
            return self.__lookuptable[key]
        elif self.__parent is not None:
            return self.__parent.dictLookup(key)
        else:
            raise KeyError('No Dictionary entry for %s' % key)
    def _dictKeys(self):
        if self.__parent is not None:
            s = self.__parent._dictKeys()
        else:
            s = set()
        return s | set(self.__lookuptable.keys())
    def dictSet(self,key,value):
        if not self.__lookuptable.has_key(key):
            self.__lookuptable[key] = value
        else:
            raise KeyError('Dictionary entry for %s already defined' % key)

    def dump(self,depth=0):
        for k,v in self.data.items():
            print '%*s = %s' % (depth*2,k,v)
        if isinstance(self.__parent,CommandDict):
            self.__parent.dump(depth+1)
        else:
            print '%*s' % (depth*2,str(self.__parent))

    def __collect(self,d):
        if self.__parent is not None:
            self.__parent.__collect(d)
        d.update(self.data)
        return d
        
    def items(self):
        return self.__collect({}).items()


class PushIterator:
    def __init__(self,buffer):
        self.__it = iter(buffer)
        self.__buffer = []
    def __iter__(self):
        return self
    def next(self):
        if self.__buffer:
            return self.__buffer.pop()
        else:
            return self.__it.next()
    def peek(self):
        if not self.__buffer:
            self.__buffer.append(self.__it.next())
        return self.__buffer[-1]
    def empty(self):
        if self.__buffer: return False
        else:
            try: 
                self.peek()
                return False
            except StopIteration: 
                return True
    def __nonzero__(self): return not self.empty()
    def pushback(self,item):
        self.__buffer.append(item)



def partListIter(l,start,stop,step=1):
    i = start
    if stop < 0: 
        stop = (- stop) % len(l)
        if stop > 0: stop = len(l) - stop
    if step < 1: step = 1
    while i < stop and i < len(l):
        yield l[i]
        i += step

class XList:
    def __init__(self,l=None):
        self.data = l or []
        self.__offset = 0
        self.__last = len(self.data)
    def __len__(self): return self.__last - self.__offset
    def __nonzero__(self): return len(self) > 0
    def __getitem__(self,idx):
        if idx + self.__offset < self.__last:
            return self.data[idx + self.__offset]
        else:
            raise IndexError("Index out of bound")

    def __iter__(self):
        return partListIter(self.data, self.__offset, self.__last)

    def pop(self,idx=-1):
        if self.__offset < self.__last:
            if idx == -1: 
                self.__last -= 1
                return self.data[self.__last]
            elif idx == 0: 
                self.__offset += 1
                return self.data[self.__offset-1]
            else:
                raise IndexError("Invalid index to pop")
        else:
            raise IndexError('Empty list')
    def append(self,item):
        if self.__last < len(self.data):
            self.data[self.__last] = item
        else:
            self.data.append(item)
        self.__last += 1
            
            



class CompressWrap:
    def __init__(self,filename,timestamp):
        self.filename = filename
        self.timestamp = timestamp
    def write(self,filename,archname):
        pass
    def writestr(self,archname,data):
        pass
    def close(self):
        pass

class ZipWrap(CompressWrap):
    def __init__(self,filename,timestamp):
        CompressWrap.__init__(self,filename,timestamp)
        self.__zipfile = zipfile.ZipFile(filename,"w")
        self.__timestamp = timestamp
    def write(self,filename,archname):
        f = open(filename,'rb')
        try:
            data = f.read()
            self.writestr(data,archname)
        finally:
            f.close()
    def writestr(self,data,archname):
        zi = zipfile.ZipInfo(archname)
        zi.internal_attr |= 1 # text file
        zi.external_attr = 0x81a40001 #0x80000001 + (0644 << 16). Permissions
        zi.date_time =  time.localtime(self.__timestamp)[:6]
        self.__zipfile.writestr(zi,str(data))
    def close(self):
        self.__zipfile.close()
        
class TarWrap(CompressWrap):
    def __init__(self,filename,timestamp,compress=""):
        CompressWrap.__init__(self,filename,timestamp)
        mode = 'w|%s' % compress
        self.__timestamp = timestamp
        self.__file = open(filename,'wb')
        #self.__tarfile = tarfile.open(filename,mode)
        self.__tarfile = tarfile.open(fileobj=self.__file,mode=mode)
            
    def write(self,filename,arcname):

        f = open(filename,'rb')
        try:
            ti = tarfile.TarInfo(arcname)
            ti.mode = 0644
            ti.size = os.fstat(f.fileno()).st_size
            ti.mtime = self.__timestamp
            self.__tarfile.addfile(ti, f)
        finally:
            f.close() 
    
    def writestr(self,data,arcname):
        f = tempfile.TemporaryFile('w+b')
        try:
            f.write(str(data))
            f.flush()
            f.seek(0)
            
            ti = tarfile.TarInfo(arcname)
            ti.mode = 0644
            ti.size = os.fstat(f.fileno()).st_size
            ti.mtime = int(self.__timestamp)
            ti.size = len(data)
            self.__tarfile.addfile(ti,f)
        finally: 
            f.close()
    def close(self):
        self.__tarfile.close()
        self.__file.close()

class TextStringList:
    def __init__(self,lines):
        assert lines
        assert isinstance(lines,list)
        self.data = lines
        
    def __str__(self):
        r = []
        for s in self.data:
            if isinstance(s,unicode):
                r.append(s.encode('utf-8'))
            else:
                r.append(s)
        return ''.join(r)
    def __len__(self):
      return sum([ len(s) for s in self.data])
        

class ThreadedTarWrap(CompressWrap):
    def __init__(self,filename,timestamp,compress=""):
        CompressWrap.__init__(self,filename,timestamp)
        mode = 'w|%s' % compress
        self.__timestamp = timestamp
        self.__file = open(filename,'wb')
        #self.__tarfile = tarfile.open(filename,mode)
        self.__tarfile = tarfile.open(fileobj=self.__file,mode=mode)

        self.__thread = threading.Thread(target=self.__run)
        self.__qwaitcond = threading.Condition()
        self.__queue = collections.deque()
        self.__thread.start()

    def __push(self,item):
        self.__qwaitcond.acquire()
        self.__queue.append(item)
        self.__qwaitcond.notify()
        self.__qwaitcond.release()
    def __pop(self):
        self.__qwaitcond.acquire()
        if len(self.__queue) == 0:
            self.__qwaitcond.wait()
        res = self.__queue.popleft()
        self.__qwaitcond.release()
        return res
            
    def __run(self):
        pop = self.__pop

        while True:
            item = pop()
            if item == None:
                break
            else:
                data, filename, arcname = item
                #print " ---> %s" % arcname
                if data is not None:
                    self.__writestr(str(data),arcname)
                else:
                    self.__write(filename,arcname)
    def write(self,filename,arcname):
        self.__push((None,filename,arcname))
    def writestr(self,data,arcname):
        self.__push((data,None,arcname))
    def __write(self,filename,arcname):

        f = open(filename,'rb')
        try:
            ti = tarfile.TarInfo(arcname)
            ti.mode = 0644
            ti.size = os.fstat(f.fileno()).st_size
            ti.mtime = self.__timestamp
            self.__tarfile.addfile(ti, f)
        finally:
            f.close() 
    
    def __writestr(self,data,arcname):
        f = tempfile.TemporaryFile('w+b')
        try:
            f.write(str(data))
            f.flush()
            f.seek(0)
            
            ti = tarfile.TarInfo(arcname)
            ti.mode = 0644
            ti.size = os.fstat(f.fileno()).st_size
            ti.mtime = int(self.__timestamp)
            ti.size = len(data)
            self.__tarfile.addfile(ti,f)
        finally: 
            f.close()
    def close(self):
        self.__push(None)
        self.__thread.join()
        
        self.__tarfile.close()
        self.__file.close()


class DirWrap(CompressWrap):
    def __init__(self,dirname,timestamp):
        CompressWrap.__init__(self,dirname,timestamp)
        self.__basedir = dirname 
        self.__filename = dirname + '.tar'
        self.__timestamp = timestamp

    def write(self,filename,arcname):
        fname = os.path.join(self.__basedir,arcname)
        dname = os.path.dirname(fname)
        try: os.makedirs(dname)
        except: pass
        outf = open(fname,'wb')
        try:
            inf = open(filename,'rb')
            try:
                outf.write(inf.read())
                outf.flush()
            finally: 
                inf.close()
        finally:
            outf.close()

    def writestr(self,data,arcname):
        fname = os.path.join(self.__basedir,arcname)
        dname = os.path.dirname(fname)
        try: os.makedirs(dname)
        except: pass
        
        outf = open(fname,'wb')
        try:
            outf.write(str(data))
        finally:
            outf.close()
            st = os.stat(fname)
            atime = st[stat.ST_ATIME] #access time
            os.utime(fname,(atime,int(self.__timestamp)))
    

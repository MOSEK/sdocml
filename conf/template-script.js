function recalc_size()
{
  var winheight = window.innerHeight;
  var node = document.getElementById("template-middle-box-scaler");
  var footerNode = document.getElementById('template-footer-box');

  var footerHeight = footerNode.clientHeight;
  var newHeight = (winheight - footerHeight 
                    - 41 // header height
                    - 29 // tab height
                    - 10 // Some extra space
                    )

  node.style.height = newHeight + "px";
  node.style.maxHeight = newHeight + "px";


  var sidebarNode  = document.getElementById("template-sidebar");

  var mainNode = document.getElementById("template-main-body");
  if (sidebarNode.style == "none")
  {
    mainNode.style.width = node.clientWidth + 'px';
    mainNode.style.maxWidth = node.clientWidth + 'px';
  }
  else
  {
    mainNode.style.width = (node.clientWidth - sidebarNode.clientWidth - 5) + 'px';
    mainNode.style.maxWidth = (node.clientWidth - sidebarNode.clientWidth - 5) + 'px';
  }
}

function toggle_sidebar()
{
  var node = document.getElementById("template-sidebar");
  if (node.style.display == 'none')
  {
    node.style.display = "block";
  }
  else
  {
    node.style.display = "none";
  }
  window.onresize();
}

function show_sidebar_item(which)
{
  var nodeContent = document.getElementById("template-sidebar-content-frame");
  var nodeIndex   = document.getElementById("template-sidebar-index-frame");

  if (which == "index")
  {
    nodeIndex.style.display   = "block";
    nodeContent.style.display = "none";
  }
  else if (which == "content")
  {
    nodeIndex.style.display   = "none";
    nodeContent.style.display = "block";
  }
}


function debug(msg)
{
  var n = document.getElementById('debug');
  if ( n != null)
  {
    n.innerHTML = n.innerHTML + msg + '\n';
  }
}



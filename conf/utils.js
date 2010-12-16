function _showItem(id)
{
    var elm = document.getElementById(id);
    elm.style.display = "block";
}
function _hideItem(id)
{
    var elm = document.getElementById(id);
    elm.style.display = "none";
}

function toggleDisplayBlock(id)
{ 
    var elm = document.getElementById(id);
    if (elm.style.display != "none")
    {
        elm.style.display = "none";
    }
    else
    {
        elm.style.display = "block";
    }
}

function toggleLineNumbers(id)
{
    var elm = document.getElementById(id);
    
    for (n=elm.firstChild; n != null; n = n.nextSibling)
    {
        if (n.nodeName == "SPAN"
            && n.attributes.getNamedItem("class").value == "line-no"
            )
        {
            if (n.style.display == "none")
                n.style.display = "inline";
            else
                n.style.display = "none";
        }
    }
}


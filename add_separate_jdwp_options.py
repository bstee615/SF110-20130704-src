"""
This script adds an Ant target, evosuite-trace, which waits for a debugger then executes the tests.
Must specify an option ${traced.classname}, which sets the classname whose tests we want to execute.
The fully-qualified name must be supplied (you can get from classes.txt) in filepath-format -- see example.
The target and option can be activated like so:

ant evosuite-trace -Dtraced.classname=com/ib/client/AnyWrapperMsgGenerator # Example with 1_tullibee
"""

from lxml import etree
from pathlib import Path
from copy import deepcopy

build_xmls = list(Path(".").glob("*_*/build.xml"))
build_xmls = [x for x in build_xmls if x.parent.name.startswith("1_")] # DEBUG

count = 0
for xml in build_xmls:
    # Load the XML file
    tree = etree.parse(xml)
    root = tree.getroot()

    # Add commandline option
    element = etree.Element("property", name="traced.classname", value="false")
    element.tail = "\n  \n  "
    root.insert(0, element)
    comment = etree.Comment(" Properties for trace modeling ")
    comment.tail = "\n  "
    root.insert(0, comment)

    # Add conditional for evosuite-test task
    test_element = root.find("./target[@name='evosuite-test']")

    # Executed when the option is given
    trace_element = deepcopy(test_element)
    trace_element.attrib["name"] = "evosuite-trace"
    trace_element.attrib["description"] = "Run EvoSuite generated tests and wait for tracer to attach"
    junit_element = trace_element.find("./junit")
    jvm_arguments = etree.fromstring("""<root><jvmarg value="-Xdebug" />
        <jvmarg value="-Xnoagent" />
        <jvmarg value="-Djava.compiler=NONE" />
        <jvmarg value="-Xrunjdwp:transport=dt_socket,address=8787,timeout=60000,server=y,suspend=y" />
        </root>""")
    for c in jvm_arguments:
        junit_element.insert(0, c)
    
    junit_element = trace_element.find("./junit")
    classpath_element = junit_element.find("./classpath")
    fileset_element = junit_element.find("./batchtest/fileset")
    fileset_element.attrib["dir"] = "${evosuite.java}"
    for child in list(fileset_element):
        fileset_element.remove(child)
    include_element = etree.Element("include", name="${traced.classname}_ESTest.java")
    include_element.tail = "\n             "
    fileset_element.append(include_element)
    if fileset_element.find("./exclude[@name='**/*_scaffolding.java']") is None:
        exclude_element = etree.Element("exclude", name="**/*_scaffolding.java")
        fileset_element.append(exclude_element)
        exclude_element.tail = "\n           "

    # Insert conditions after original evosuite-test element
    root.insert(root.index(test_element)+1, trace_element)

    # Save the modified XML tree back to the file
    tree.write(xml, encoding="utf-8", xml_declaration=True)
    count += 1

print(count, "changes applied")

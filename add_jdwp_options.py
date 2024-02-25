"""
DEPRECATED; use add_separate_jdwp_options.py instead.

This script adds an option ${traced.wait}, which causes Ant-JUnit to wait for a debugger before executing tests.
By default, the option is "false", so the build.xml behaves like the original.
The option can be activated like so:

ant evosuite-test -Dtraced.wait=true
"""

from lxml import etree
from pathlib import Path
from copy import deepcopy

build_xmls = list(Path(".").glob("*_*/build.xml"))

count = 0
for xml in build_xmls:
    # Load the XML file
    tree = etree.parse(xml)
    root = tree.getroot()

    # Add commandline option
    element = etree.Element("property", name="traced.wait", value="false")
    element.tail = "\n  \n  "
    root.insert(0, element)
    comment = etree.Comment(" Properties for trace modeling ")
    comment.tail = "\n  "
    root.insert(0, comment)

    # Add conditional for evosuite-test task
    test_element = root.find("./target[@name='evosuite-test']")

    # Executed when the option is given
    true_element = deepcopy(test_element)
    true_element.attrib["name"] = "evosuite-test-true"
    true_element.attrib["if"] = "${traced.wait}"
    junit_element = true_element.find("./junit")
    jvm_arguments = etree.fromstring("""<root><jvmarg value="-Xdebug" />
        <jvmarg value="-Xnoagent" />
        <jvmarg value="-Djava.compiler=NONE" />
        <jvmarg value="-Xrunjdwp:transport=dt_socket,address=8787,timeout=60000,server=y,suspend=y" />
        </root>""")
    for c in jvm_arguments:
        junit_element.insert(0, c)

    # Executed by default
    false_element = deepcopy(test_element)
    false_element.attrib["name"] = "evosuite-test-false"
    false_element.attrib["unless"] = "${traced.wait}"

    # Set up test element as conditional branch
    test_element.text = None
    for child in test_element:
        test_element.remove(child)
    test_element.attrib["depends"] = "evosuite-test-true, evosuite-test-false"
    
    # Insert conditions after original evosuite-test element
    root.insert(root.index(test_element)+1, false_element)
    root.insert(root.index(test_element)+1, true_element)

    # Save the modified XML tree back to the file
    tree.write(xml, encoding="utf-8", xml_declaration=True)
    count += 1

print(count, "changes applied")

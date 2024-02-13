from lxml import etree
from pathlib import Path

build_xmls = list(Path(".").glob("*_*/build.xml"))

count = 0
for xml in build_xmls:
    # Load the XML file
    tree = etree.parse(xml)
    root = tree.getroot()

    # Add a child element to <path> with id="test.lib"
    path_element = root.find("./path[@id='test.lib']")
    if path_element.find("./pathelement[@location='${lib.dir}/hamcrest-core-1.3.jar']") is None:
        new_child = etree.Element("pathelement", location="${lib.dir}/hamcrest-core-1.3.jar")
        path_element.append(new_child)

    # Replace location in <path> with id="evosuite.lib"
    path_element = root.find("./path[@id='evosuite.lib']")
    if path_element.find("./pathelement[@location='${lib.dir}/evosuite.jar']") is not None:
        path_element.attrib["location"] = "${lib.dir}/evosuite-1.0.6.jar"

    # Add evosuite.lib to target compile-tests
    classpath_element = root.find("./target[@name='compile-tests']/javac/classpath")
    if path_element.find("./path[@refid='evosuite.lib']") is None:
        new_classpath_child = etree.Element("path", refid="evosuite.lib")
        classpath_element.append(new_classpath_child)

    # Add paths to evosuite-test target and point to evosuite tests
    junit_element = root.find("./target[@name='evosuite-test']/junit")
    classpath_element = junit_element.find("./classpath")
    if path_element.find("./path[@refid='evosuite.lib']") is None:
        new_classpath_child = etree.Element("path", refid="evosuite.lib")
        classpath_element.append(new_classpath_child)
    fileset_element = junit_element.find("./batchtest/fileset")
    fileset_element.attrib["dir"] = "${evosuite.java}"
    if fileset_element.find("./exclude[@name='**/*_scaffolding.java']") is None:
        new_fileset_child = etree.Element("exclude", name="**/*_scaffolding.java")
        fileset_element.append(new_fileset_child)

    # Save the modified XML tree back to the file
    tree.write(xml, encoding="utf-8", xml_declaration=True)
    count += 1

print(count, "fixes applied")

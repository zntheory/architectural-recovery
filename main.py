import os
import sys
import pip
from exceptiongroup import catch
from git import Repo
import re
import pathlib
from pathlib import Path
import networkx as nx
import matplotlib.pyplot as plt
import ast


# Inspo credit
# https://colab.research.google.com/drive/1ohvPB_SZeDa5NblzxLAkwmTY8JZRBZe_?usp=sharing#scrollTo=Ssb7D6FsoD6F

# -- variables --

# current working dir
cwd = os.getcwd()
print ("Current working dir: " + cwd)
CODE_ROOT_FOLDER = cwd + "/api/"
print ("Code root folder: " + CODE_ROOT_FOLDER)


# -- helper functions --

# helper function to get a file path w/o having to always provide the /content/zeeguu-api/ prefix
def file_path(file_name):
    return CODE_ROOT_FOLDER+file_name


# extracting a module name from a file name
def module_name_from_file_path(full_path):
    file_name = full_path[len(CODE_ROOT_FOLDER):]
    file_name = file_name.replace("/__init__.py","")
    file_name = file_name.replace("/",".")
    file_name = file_name.replace(".py","")
    return file_name

# Naive import extraction
# TODO: Add full support for imports
def import_from_line(line):

    # regex patterns used
    #   ^  - beginning of line
    #   \S - anything that is not space
    #   +  - at least one occurrence of previous
    #  ( ) - capture group (read more at: https://pynative.com/python-regex-capturing-groups/)
    try:
        y = re.search(r"^from (\S+)", line)
        if not y:
            y = re.search(r"^import (\S+)", line)
        return y.group(1)
    except:
        return None

# Extract a file's modules
# Extraction ex: zeeguu_core.model.bookmark
def imports_from_file_regex(file):

    all_imports = []

    lines = [line for line in open(file)]

    for line in lines:
        imp = import_from_line(line)

        if imp:
            all_imports.append(imp)

    return all_imports

def get_source_tree_from_file(_file_path):
    source = open(_file_path).read()
    tree = ast.parse(source)
    return tree

def imports_from_file(tree):

    all_imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                all_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            all_imports.append(node.module)
    return all_imports

# Extract files' dependencies
def dependencies_graph(code_root_folder):
    files = Path(code_root_folder).rglob("*.py")

    G = nx.Graph()

    for file in files:
        _file_path = str(file)

        module_name = module_name_from_file_path(_file_path)

        if module_name not in G.nodes:
            G.add_node(module_name)

        for each in imports_from_file(_file_path):
            G.add_edge(module_name, each)
    return G

# Draw network graph
def draw_graph(G, size, **args):
    plt.figure(figsize=size)
    nx.draw_kamada_kawai(G, **args)
    #plt.show()
    plt.savefig("figure.png")

def relevant_module(module_name):

    # Due to `from . import api, db_session` in api/zeegu/api/endpoints/reading_sessions.py
    # I decided to simply evaluate these types of imports as irrelevant.
    # This generally happens when `from .` is used, which was mostly used in init-files.
    # In these cases, it is okay to ignore them for our purposes.
    if module_name is None:
        return False

    if "test" in module_name:
        return False

    if module_name.startswith("zeeguu"):
        return True

    return False

def dependencies_digraph(code_root_folder):
    files = Path(code_root_folder).rglob("*.py")

    G = nx.DiGraph()

    for file in files:
        file_path = str(file)
        print("File path: " + file_path)

        source_module = module_name_from_file_path(file_path)
        print("Source module: " + source_module)
        if not relevant_module(source_module):
          continue

        if source_module not in G.nodes:
            G.add_node(source_module)

        use_tree = True

        try:
            tree = get_source_tree_from_file(file_path)
        except:
            use_tree = False
        finally:
            if use_tree:
                for target_module in imports_from_file(tree):
                    if target_module is not None: print("Target module: " + target_module)
                    if relevant_module(target_module):
                        G.add_edge(source_module, target_module)
            else:
                for target_module in imports_from_file_regex(file_path):
                    if target_module is not None: print("Target module: " + target_module)
                    if relevant_module(target_module):
                        G.add_edge(source_module, target_module)


    return G

def top_level_package(module_name, depth=1):
    components = module_name.split(".")
    return ".".join(components[:depth])

def abstracted_to_top_level(G, depth=1):
    aG = nx.DiGraph()
    for each in G.edges():
        src = top_level_package(each[0], depth)
        dst = top_level_package(each[1], depth)

        if src != dst:
          aG.add_edge(src, dst)

    return aG

def main():
    # print(sys.version)

    # !{sys.executable} -m pip install gitpython/pyvis
    # pip.main(['install', '-r', 'requirements.txt'])

    # print(cwd)
    # print(file_path("zeeguu/core/model/user.py"))

    # Had to insert api/ between zeeguu-api/ and zeeguu/
    #print(cwd +"/api/zeeguu/core/model/user.py")
    #print (file_path("zeeguu/core/model/user.py"))
    assert (file_path("zeeguu/core/model/user.py") == cwd + "/api/" + "zeeguu/core/model/user.py")
    assert 'zeeguu.core.model.user' == module_name_from_file_path(file_path('zeeguu/core/model/user.py'))

    # test
    #imports_from_file(file_path('/zeeguu/core/model/user.py'))
    #print(imports_from_file(file_path('zeeguu/core/model/bookmark.py')))
    #print(imports_from_file(file_path('zeeguu/core/model/unique_code.py')))

    # run it

    DG = dependencies_digraph(CODE_ROOT_FOLDER)
    ADG = abstracted_to_top_level(DG, 3)
    print(ADG.number_of_nodes())
    #draw_graph(ADG, (10, 10), with_labels=True)

    assert (top_level_package("zeeguu.core.model.util", 1) == "zeeguu")
    assert (top_level_package("zeeguu.core.model.util", 2) == "zeeguu.core")

main()
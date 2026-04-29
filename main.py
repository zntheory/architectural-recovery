import os
import sys
import pip
from git import Repo
import re
import pathlib
from pathlib import Path
import networkx as nx
import matplotlib.pyplot as plt


# Inspo credit
# https://colab.research.google.com/drive/1ohvPB_SZeDa5NblzxLAkwmTY8JZRBZe_?usp=sharing#scrollTo=Ssb7D6FsoD6F

# -- variables --

# current working dir
cwd = os.getcwd()
# repo to clone
CODE_ROOT_FOLDER="/content/zeeguu-api/"

# -- helper functions --

def file_path(file_name):
    return CODE_ROOT_FOLDER+file_name

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
        y = re.search("^from (\S+)", line)
        if not y:
            y = re.search("^import (\S+)", line)
        return y.group(1)
    except:
        return None

# Extract a file's modules
# Extraction ex: zeeguu_core.model.bookmark
def imports_from_file(file):

    all_imports = []

    lines = [line for line in open(file)]

    for line in lines:
        imp = import_from_line(line)

        if imp:
            all_imports.append(imp)

    return all_imports

# Extract files' dependencies
def dependencies_graph(code_root_folder):
    files = Path(code_root_folder).rglob("*.py")

    G = nx.Graph()

    for file in files:
        file_path = str(file)

        module_name = module_name_from_file_path(file_path)

        if module_name not in G.nodes:
            G.add_node(module_name)

        for each in imports_from_file(file_path):
            G.add_edge(module_name, each)
    return G

# Draw network graph
def draw_graph(G, size, **args):
    plt.figure(figsize=size)
    nx.draw_kamada_kawai(G, **args)
    plt.show()


def main():
    print(sys.version)

    # !{sys.executable} -m pip install gitpython/pyvis
    #pip.main(['install', '-r', 'requirements.txt'])

    print(cwd)

    # clone repo
    if not os.path.exists(CODE_ROOT_FOLDER):
        Repo.clone_from("https://github.com/zeeguu/api", CODE_ROOT_FOLDER)

    assert (file_path("zeeguu/core/model/user.py") == "/content/zeeguu-api/zeeguu/core/model/user.py")
    assert 'zeeguu.core.model.user' == module_name_from_file_path(file_path('zeeguu/core/model/user.py'))

    imports_from_file(file_path('zeeguu/core/model/user.py'))

    # test
    print(imports_from_file(file_path('zeeguu/core/model/bookmark.py')))
    print(imports_from_file(file_path('zeeguu/core/model/unique_code.py')))

    # run it
    G = dependencies_graph(CODE_ROOT_FOLDER)
    draw_graph(G, (40, 40), with_labels=False)

main()
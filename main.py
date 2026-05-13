import ast
import os
import random
import re
import sys
from pathlib import Path
from pydriller import Repository
from pydriller import ModificationType
from collections import defaultdict
import matplotlib.pyplot as plt
import networkx as nx

# Inspo credit
# https://colab.research.google.com/drive/1ohvPB_SZeDa5NblzxLAkwmTY8JZRBZe_?usp=sharing#scrollTo=Ssb7D6FsoD6F

# -- variables --

# current working dir
cwd = os.getcwd()
print ("Current working dir: " + cwd)
CODE_ROOT_FOLDER = cwd
print ("Code root folder: " + CODE_ROOT_FOLDER)
REPO_DIR = 'https://github.com/zeeguu/api'
all_commits = list(Repository(REPO_DIR).traverse_commits())

# -- helper functions --

def print_out_commit_details(commits):
  for commit in commits:
      print(commit)
      for each in commit.modified_files:
          print(f"{commit.author.name} {each.change_type} {each.filename}\n -{each.old_path}\n -{each.new_path}")

def module_name_from_rel_path(full_path):
    # e.g. ../core/model/user.py -> zeeguu.core.model.user

    file_name = full_path.replace("/__init__.py","")
    file_name = file_name.replace("/",".")
    file_name = file_name.replace(".py","")
    return file_name

# helper function to get a file path w/o having to always provide the /content/zeeguu-api/ prefix
def file_path(file_name):
    return CODE_ROOT_FOLDER+file_name


# extracting a module name from a file name
def module_name_from_file_path(full_path):
    file_name = full_path[len(CODE_ROOT_FOLDER):]
    file_name = file_name.lstrip("/")                   # removes leading slash
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
def draw_graph(G, size, commits):

    plt.figure(figsize=size)

    #pos = nx.spring_layout(
    #    G,
    #    k=2.5,
    #    iterations=100,
    #    seed=42
    #)

    pos = nx.spring_layout(
        G,
        k=20,  # larger => more spacing
        iterations=300,  # more settling
        scale=20,  # expands final coordinates
        seed=42
    )

    nx.draw_networkx_nodes(
        G,
        pos,
        node_size=commits,
        node_color='r',
    )

    nx.draw_networkx_labels(
        G,
        pos,
        font_size=10
    )

    nx.draw_networkx_edges(
        G,
        pos,
        arrows=True,
        # connectionstyle="arc3,rad=0.15"
    )

    # Edge labels
    edge_labels = nx.get_edge_attributes(G, "weight")

    nx.draw_networkx_edge_labels(
        G,
        pos,
        edge_labels=edge_labels,
        font_size=10,
        bbox=dict(
            facecolor="white",
            edgecolor="none",
            alpha=0.9
        ),
        rotate=False
    )

    plt.axis("off")

    plt.savefig(
        "../figure.png",
        bbox_inches="tight",
        dpi=300
    )

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
        #print("File path: " + file_path)

        source_module = module_name_from_file_path(file_path)
        # print("Source module: " + source_module)
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
                targets = imports_from_file(tree)
            else:
                targets = imports_from_file_regex(file_path)

            for target_module in targets:

                if relevant_module(target_module):

                    if G.has_edge(source_module, target_module):
                        G[source_module][target_module]["weight"] += 1
                    else:
                        G.add_edge(
                            source_module,
                            target_module,
                            weight=1
                        )

    return G

def top_level_package(module_name, depth=1):
    components = module_name.split(".")
    return ".".join(components[:depth])

def abstracted_to_top_level(G, depth=1):

    aG = nx.DiGraph()


    for src, dst, data in G.edges(data=True):

        src_top = top_level_package(src, depth)
        dst_top = top_level_package(dst, depth)

        #if src_top == dst_top:
        #    continue
        for node in G.nodes():
            aG.add_node(top_level_package(node, depth))

        weight = data.get("weight", 1)

        if aG.has_edge(src_top, dst_top):
            aG[src_top][dst_top]["weight"] += weight
        else:
            aG.add_edge(
                src_top,
                dst_top,
                weight=weight
            )

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
    #assert (file_path("zeeguu/core/model/user.py") == cwd + "/api/" + "zeeguu/core/model/user.py")
    #assert 'zeeguu.core.model.user' == module_name_from_file_path(file_path('zeeguu/core/model/user.py'))

    # test
    #imports_from_file(file_path('/zeeguu/core/model/user.py'))
    #print(imports_from_file(file_path('zeeguu/core/model/bookmark.py')))
    #print(imports_from_file(file_path('zeeguu/core/model/unique_code.py')))

    #print_out_commit_details(all_commits[0:1])

#    commit_counts = defaultdict(int)

#    for commit in all_commits:
#        for each in commit.modified_files:
#            try:
#                commit_counts[each.new_path] += 1
#            except:
#                pass

    commit_counts = {}

    for commit in all_commits:
        for modification in commit.modified_files:

            new_path = modification.new_path
            old_path = modification.old_path

            try:

                if modification.change_type == ModificationType.RENAME:
                    commit_counts[new_path] = commit_counts.get(old_path, 0) + 1
                    commit_counts.pop(old_path)

                elif modification.change_type == ModificationType.DELETE:
                    commit_counts.pop(old_path, '')

                elif modification.change_type == ModificationType.ADD:
                    commit_counts[new_path] = 1

                else:  # modification to existing file
                    commit_counts[old_path] += 1
            except Exception as e:
                print("something went wrong with: " + str(modification))
                pass

    sorted(commit_counts.items(), key=lambda x: x[1], reverse=True)

    # sort by number of commits in decreasing order
    # tester = sorted(commit_counts.items(), key=lambda x: x[1], reverse=True)[:42]
    #print(tester)
    # discussion: What is ("None", 103) ?

    assert ("tools.migrations.teacher_dashboard_migration_1.upgrade" == module_name_from_rel_path(
        "tools/migrations/teacher_dashboard_migration_1/upgrade.py"))
    assert ("zeeguu.api") == module_name_from_rel_path("zeeguu/api/__init__.py")

    package_activity = defaultdict(int)

    for path, count in commit_counts.items():
        if ".py" in str(path):
            l2_module = top_level_package(module_name_from_rel_path(path), 2)
            package_activity[l2_module] += count

    sorted_sizes = sorted(package_activity.items(), key=lambda x: x[1], reverse=True)
    #print(sorted_sizes)

    # run it
    DG = dependencies_digraph(CODE_ROOT_FOLDER)
    ADG = abstracted_to_top_level(DG, 2)
    #print("No. of edges: " + str(ADG.number_of_edges()))
    #print("No. of out degrees: " + str(ADG.out_degree()))
    #print("No. of out edges: " + str(ADG.out_edges()))
    #print(ADG.number_of_nodes())

    print(list(ADG.nodes()))

    sizes = [
        package_activity.get(node, 1)
        for node in ADG.nodes()
    ]

    print(sizes)

    draw_graph(ADG, (20, 20), sizes)

    #assert (top_level_package("zeeguu.core.model.util", 1) == "zeeguu")
    #assert (top_level_package("zeeguu.core.model.util", 2) == "zeeguu.core")

main()
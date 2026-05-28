import ast
import os
import random
import re
import sys
from pathlib import Path
from pydriller import Repository
from pydriller import ModificationType
from collections import defaultdict
from pyvis.network import Network
import networkx as nx
import math
from matplotlib import cm
from matplotlib import colors
from itertools import combinations

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

    file_name = full_path.replace("/__init__.py","")
    file_name = file_name.replace("/",".")
    file_name = file_name.replace(".py","")

    return normalize_module_name(file_name)

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

def normalize_module_name(module_name):

    if module_name is None:
        return None

    replacements = {
        "zeeguu_core": "zeeguu.core",
        "zeeguu_api": "zeeguu.api",
        "zeeguu.api_dev": "zeeguu.api",
        #"zeeguu_tokenizer": "zeeguu.tokenizer",
    }

    for old, new in replacements.items():
        module_name = module_name.replace(old, new)

    return module_name
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

def churn_color(churn, min_churn, max_churn):

    # Logarithmic normalization
    norm = colors.LogNorm(
        vmin=max(min_churn, 1),
        vmax=max_churn
    )

    # Reversed magma:
    # low churn = light
    # high churn = dark
    cmap = cm.get_cmap("magma_r")

    rgba = cmap(norm(churn))

    return colors.to_hex(rgba)

def color_for_legend(value, min_churn, max_churn):

    norm = colors.LogNorm(
        vmin=max(min_churn, 1),
        vmax=max_churn
    )

    cmap = cm.get_cmap("magma_r")

    return colors.to_hex(cmap(norm(value)))

# Draw network graph
def draw_graph_pyvis(G, package_activity, output_file="graph.html", directed=True):

    net = Network(
        height="900px",
        width="100%",
        directed=directed,
        bgcolor="#f5f5f5",
        font_color="#222222",
        cdn_resources="in_line"
    )

    net.barnes_hut(
        gravity=-30000,
        central_gravity=0.2,
        spring_length=250,
        spring_strength=0.01,
        damping=0.09
    )

    all_churn_values = list(package_activity.values())

    min_churn = min(all_churn_values)
    max_churn = max(all_churn_values)
    
    legend_values = [1, 10, 100, 1000, max_churn]

    legend_colors = [
        color_for_legend(v, min_churn, max_churn)
        for v in legend_values
    ]

    # Nodes
    for node in G.nodes():

        churn = package_activity.get(node, 1)

        # Adjusted for better visual differentiation
        # size = 10 + math.log1p(churn) * 10 #OLD
        size = 12 + math.log10(churn + 1) * 18

        node_color = churn_color(
            churn,
            min_churn,
            max_churn
        )

        display_label = node.removeprefix("zeeguu.")

        net.add_node(
            node,
            label=display_label,
            size=size,
            color=node_color,
            title=f"""
            <b>{node}</b><br>
            Churn: {churn}
            """
        )

    # Edges
    for src, dst, data in G.edges(data=True):

        weight = data.get("weight", 1)

    for src, dst, data in G.edges(data=True):

            weight = data.get("weight", 1)

            edge_kwargs = {
                "value": weight,
                "width": max(1, math.log1p(weight) * 2),
                "label": str(weight),
                "title": f"Weight: {weight}",
            }

            # Only add arrows for directed graphs
            if directed:
                edge_kwargs["arrows"] = "to"

            net.add_edge(
                src,
                dst,
                **edge_kwargs
            )

    net.show_buttons(filter_=['physics'])

    html = net.generate_html()

    legend_html = f"""
    <div style="
    position: fixed;
    bottom: 20px;
    left: 20px;
    width: 280px;
    background-color: white;
    padding: 12px;
    border: 1px solid #999;
    border-radius: 8px;
    z-index: 9999;
    font-family: Arial;
    box-shadow: 0 2px 10px rgba(0,0,0,0.15);
    ">

    <h4 style="margin:0 0 10px 0; color:black;">
    Churn - no. of commits (log scale)
    </h4>

    <div style="
    height: 24px;
    background: linear-gradient(
    to right,
    {legend_colors[0]},
    {legend_colors[1]},
    {legend_colors[2]},
    {legend_colors[3]},
    {legend_colors[4]}
    );
    border:1px solid black;
    border-radius:4px;
    "></div>

    <div style="
    display:flex;
    justify-content:space-between;
    font-size:12px;
    margin-top:6px;
    color:black;
    ">
    <span>1</span>
    <span>10</span>
    <span>100</span>
    <span>1000</span>
    <span>{int(max_churn)}</span>
    </div>

    </div>
    """

    html = html.replace("</body>", legend_html + "</body>")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Saved graph to {output_file}")

    
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

                target_module = normalize_module_name(target_module)
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

    # Ignore modules that are too shallow
    if len(components) < depth:
        return None

    return ".".join(components[:depth])

def abstracted_to_top_level(G, depth=1):

    aG = nx.DiGraph()

    # Add nodes once
    for node in G.nodes():

        top_node = top_level_package(node, depth)

        if top_node is None:
            continue

        aG.add_node(top_node)

    # Add edges
    for src, dst, data in G.edges(data=True):

        src_top = top_level_package(src, depth)
        dst_top = top_level_package(dst, depth)

        if src_top is None or dst_top is None:
            continue

        # To avoid reflexive edges for imports within same package
        if src_top == dst_top:
            continue

        weight = data.get("weight", 1)

        if aG.has_edge(src_top, dst_top):
            aG[src_top][dst_top]["weight"] += weight
        else:
            aG.add_edge(src_top, dst_top, weight=weight)

    return aG

def logical_dependencies_graph(commits, depth=2):

    G = nx.Graph()

    for commit in commits:

        try:
            modifications = commit.modified_files
        except Exception as e:
            print(f"Skipping commit {commit.hash}: {e}")
            continue

        changed_modules = set()

        for modification in modifications:

            path = modification.new_path or modification.old_path

            if path is None:
                continue

            if ".py" not in path:
                continue

            module_name = module_name_from_rel_path(path)

            if not relevant_module(module_name):
                continue

            abstracted_module = top_level_package(
                module_name,
                depth
            )

            if abstracted_module is None:
                continue

            changed_modules.add(abstracted_module)

        # Create edges between all modules changed together
        for mod1, mod2 in combinations(sorted(changed_modules), 2):

            if G.has_edge(mod1, mod2):
                G[mod1][mod2]["weight"] += 1
            else:
                G.add_edge(mod1, mod2, weight=1)

    return G

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

        try:
            modifications = commit.modified_files
        except Exception as e:
            print(f"Skipping commit {commit.hash}: {e}")
            continue

        for modification in modifications:

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
    print("package activity: ", package_activity)

    for path, count in commit_counts.items():
        if ".py" in str(path):
            l2_module = top_level_package(module_name_from_rel_path(path), 2)
            if l2_module is None:
                continue
            package_activity[l2_module] += count

    sorted_sizes = sorted(package_activity.items(), key=lambda x: x[1], reverse=True)
    #print(sorted_sizes)


    depth = 3

    # run it
    DG = dependencies_digraph(CODE_ROOT_FOLDER)
    ADG = abstracted_to_top_level(DG, depth=depth)
    #print("No. of edges: " + str(ADG.number_of_edges()))
    #print("No. of out degrees: " + str(ADG.out_degree()))
    #print("No. of out edges: " + str(ADG.out_edges()))
    #print(ADG.number_of_nodes())


    sizes = [
        package_activity.get(node, 1)
        for node in ADG.nodes()
    ]

    draw_graph_pyvis(ADG, package_activity, output_file="dependencies"+str(depth)+".html", directed=True)

    #assert (top_level_package("zeeguu.core.model.util", 1) == "zeeguu")
    #assert (top_level_package("zeeguu.core.model.util", 2) == "zeeguu.core")


    # Logical dependencies graph - modules that tend to change together
    LDG = logical_dependencies_graph(all_commits, depth=depth)

    draw_graph_pyvis(LDG, package_activity, output_file="logical_dependencies"+str(depth)+".html", directed=False)

main()
test_data = r"""
NodeName : 1 = Depth
NodeName : 2 = CameraState
NodeName : 3 = RegisteredColor
NodeName : 4 = Undistorted Depth
NodeName : 5 = Color
NodeName : 6 = IR
NodeCreate : 10
> Node = 1
> Type = VarNode
NodeCreate : 20
> Node = 2
> Type = VarNode
NodeDestroy : 30
> Node = 2
NodeEvaluateBegin : 40
> Node = 1
> Transaction = 3
> Thread = 140012377925376
NodeEvaluateEnd : 50
> Node = 1
> Transaction = 3
> Thread = 140012377925376
NodePulse : 60
> Node = 1
> Transaction = 3
InputNodeAdmission : 60
> Node = 1
> Transaction = 4
NodeCreate : 70
> Node = 3
> Type = VarNode
NodeAttach : 80
> Node = 1
> Parent = 3
NodeIdlePulse : 90
> Node = 3
> Transaction = 1
NodeDetach : 100
> Node = 1
> Parent = 3
"""

import networkx as nx
from lark import Lark
from lark import Transformer, Tree
import matplotlib.pyplot as plt


grammer = r"""
start: node+

node: "NodeName :" nodeid "=" NODENAME                             -> name
    | "NodeCreate :" time nodeid nodetype                       -> create
    | "NodeDestroy :" time nodeid                               -> destroy
    | "NodeEvaluateBegin :" time nodeid transactionid threadid  -> eval_begin
    | "NodeEvaluateEnd :" time nodeid transactionid threadid    -> eval_end
    | "InputNodeAdmission :" time nodeid transactionid          -> input_admission
    | "NodePulse :" time nodeid transactionid                   -> pulse
    | "NodeIdlePulse :" time nodeid transactionid               -> idle_pulse
    | "NodeAttach :" time nodeid parentid                       -> attach
    | "NodeDetach :" time nodeid parentid                       -> detach

COMMENT:       "#" /(.)+/ NL
NODENAME:      /(.)+/ NL
time:          INT
nodetype:      "> Type =" WORD
nodeid:        "> Node =" INT
             | INT
transactionid: "> Transaction =" INT
threadid:      "> Thread =" INT
parentid:      "> Parent =" INT

%import common.WORD
%import common.INT
%import common.WS
%import common.NEWLINE -> NL
%ignore WS
%ignore COMMENT
%ignore NL

"""

# class Node():
#     def __init__(self, time) -> None:
#         self.time = time
#
#
# class CreateNode(Node):
#     def __init__(self, time, id, type) -> None:
#         super().__init__(time)
#         self.id = id
#         self.type = type
#
#
# class DestroyNode(Node):
#     def __init__(self, time, id) -> None:
#         super().__init__(time)
#         self.id = id


graph = nx.DiGraph()
def drawGraph():
    pos=nx.spring_layout(graph)
    nx.draw(graph, pos=pos)
    nx.draw_networkx_labels(graph, pos=pos)

nodenames = {}
def get_name(node):
    return nodenames.get(node, node)

class PrimitiveReplace(Transformer):
    def name(self, content):
        nodenames[content[0]] = content[1]
        return content

    def time(self, n):
        return int(n[0])

    def nodetype(self, n):
        return str(n[0])

    def nodeid(self, n):
        return int(n[0])

    def transactionid(self, n):
        return int(n[0])

    def threadid(self, n):
        return int(n[0])

    def parentid(self, n):
        return int(n[0])


# somehow I can't include the visitor, using a transformer instead
class GraphVisitor(Transformer):
    """
    Transform a parsed tree to a nx graph
    """

    def __init__(self, executeCount = None) -> None:
        super().__init__()
        self.currentExec = 0
        self.maxExec = executeCount

    def transform(self, tree):
        items = []
        for c in tree.children:
            if self.currentExec > self.maxExec:
                return
            try:
                items.append(self.transform(c) if isinstance(c, Tree) else c)
            except Discard:
                pass
        try:
            f = self._get_func(tree.data)
        except AttributeError:
            return self.__default__(tree.data, items)
        else:
            self.currentExec = self.currentExec + 1
            return f(items)

    def create(self, content):
        graph.add_node(get_name(content[1]), node_type=content[2])
        #drawGraph()
        return "CREATE: ", content

    def destroy(self, content):
        graph.remove_node(get_name(content[1]))
        #drawGraph()
        return "DESTROY: ", content

    def eval_begin(self, content):
        return "E_BEGIN: ", content

    def eval_end(self, content):
        return "E_END: ", content

    def input_admission(self, content):
        return "INPUT_ADMISSION: ", content

    def pulse(self, content):
        #drawGraph()
        return "PULSE: ", content

    def idle_pulse(self, content):
        return "PULSE_IDLE: ", content

    def attach(self, content):
        graph.add_edge(get_name(content[2]), get_name(content[1]))
        #drawGraph()
        return "ATTACH: ", content

    def detach(self, content):
        graph.remove_edge(get_name(content[2]), get_name(content[1]))
        #drawGraph()
        return "DETACH: ", content

l = Lark(grammer)
#print(l.parse(test_data).pretty())
#print(GraphVisitor().transform(PrimitiveReplace().transform(l.parse(test_data))))

commandtree = []
preparedTree = []
with open("log.txt") as f:
    commandtree = l.parse(f.read())
    preparedTree = PrimitiveReplace().transform(commandtree)
    #GraphVisitor().transform(PrimitiveReplace().transform(commandtree))




from matplotlib.widgets import Slider, Button, RadioButtons
fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.25)

axcolor = 'lightgoldenrodyellow'
axtime = plt.axes([0.25, 0.1, 0.65, 0.03], facecolor=axcolor)

commandCount = len(commandtree.children)
stime = Slider(axtime, 'Step', 0, commandCount, valinit=0)

def update(val):
    t = stime.val
    graph.clear()
    GraphVisitor(executeCount = t).transform(preparedTree)
    pos=nx.spring_layout(graph)
    ax.cla()
    nx.draw(graph, pos=pos, ax=ax)
    nx.draw_networkx_labels(graph, pos=pos, ax=ax)
    fig.canvas.draw_idle()
stime.on_changed(update)

# button
# resetax = plt.axes([0.8, 0.025, 0.1, 0.04])
# button = Button(resetax, 'Reset', color=axcolor, hovercolor='0.975'),
# def reset(event):
#     print("btn")
# button.on_clicked(reset)

plt.show()

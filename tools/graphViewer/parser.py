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

import numpy as np
import networkx as nx
from lark import Lark
from lark import Transformer, Tree
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button, RadioButtons
import pydot


grammer = r"""
start: node+

node: "NodeName :" nodeid "=" NODENAME                          -> name
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


nodenames = {} # will not be reset, we just need them once
nodeupdates = {}
nodetimes = {}
graph = nx.DiGraph()
# node positions in graph
last_pos = None
# last time any node did something, used for marking active nodes
lastActive = 0
lastCommand = None
currentTurn = 0
turnStart = 0

def reset_():
    global nodeupdates, nodetimes, last_pos, lastActive, lastCommand, currentTurn, turnStart
    nodeupdates = {}
    nodetimes = {}
    graph.clear()
    last_pos = None
    lastActive = 0
    lastCommand = None
    currentTurn = 0
    turnStart = 0

reset_()

def get_name(node):
    return nodenames.get(node, node)


def updateTurn(time, transactionID):
    global currentTurn, turnStart
    if currentTurn < transactionID:
        turntime = time - turnStart
        print ("Finished turn {} in {}ms".format(currentTurn, turntime/1000.0))
        currentTurn = transactionID
        turnStart = time


class PrimitiveReplace(Transformer):
    def name(self, content):
        nodenames[content[0]] = str(content[1])
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
        if self.maxExec is not None and self.currentExec > self.maxExec:
            return

        global lastCommand
        lastCommand = tree

        for c in tree.children:
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
        global lastActive
        lastActive = content[0]
        graph.add_node(get_name(content[1]), node_type=content[2], start_time=content[0], id=content[1])
        return "CREATE: ", content

    def destroy(self, content):
        global lastActive
        lastActive = content[0]
        # add deletion time to node
        graph.add_node(get_name(content[1]), end_time=content[0])
        #graph.remove_node(get_name(content[1]))
        return "DESTROY: ", content

    def eval_begin(self, content):
        global lastActive
        updateTurn(content[0], content[2])
        lastActive = content[0]
        nodeupdates[content[1]] = nodeupdates.get(content[1], 0) + 1
        graph.nodes[get_name(content[1])]['laststart'] = content[0]
        return "E_BEGIN: ", content

    def eval_end(self, content):
        global lastActive
        updateTurn(content[0], content[2])
        lastActive = content[0]
        timings = nodetimes.get(content[1], [])
        starttime = graph.nodes[get_name(content[1])]['laststart']
        graph.nodes[get_name(content[1])]['lastend'] = content[0]
        timings.append(content[0] - starttime)
        nodetimes[content[1]] = timings

        # add stats to node
        ms_median = np.median(nodetimes[content[1]]) / 1000.0
        ms_min = np.max(nodetimes[content[1]]) / 1000.0
        ms_max = np.min(nodetimes[content[1]]) / 1000.0
        num_evals = nodeupdates[content[1]]
        graph.add_node(get_name(content[1]),
                       ms_median=float(ms_median),
                       ms_min=float(ms_min),
                       ms_max=float(ms_max),
                       num_evals=int(num_evals))

        return "E_END: ", content

    def input_admission(self, content):
        global lastActive
        updateTurn(content[0], content[2])
        lastActive = content[0]
        graph.nodes[get_name(content[1])]['inputadmission'] = content[0]
        return "INPUT_ADMISSION: ", content

    def pulse(self, content):
        global lastActive
        updateTurn(content[0], content[2])
        lastActive = content[0]
        return "PULSE: ", content

    def idle_pulse(self, content):
        global lastActive
        updateTurn(content[0], content[2])
        lastActive = content[0]
        return "PULSE_IDLE: ", content

    def attach(self, content):
        global lastActive
        lastActive = content[0]
        graph.add_edge(get_name(content[2]), get_name(content[1]))
        return "ATTACH: ", content

    def detach(self, content):
        global lastActive
        lastActive = content[0]
        graph.remove_edge(get_name(content[2]), get_name(content[1]))
        return "DETACH: ", content

l = Lark(grammer)
#print(l.parse(test_data).pretty())
#print(GraphVisitor().transform(PrimitiveReplace().transform(l.parse(test_data))))



commandtree = []
preparedTree = []
with open("log.txt") as f:
    commandtree = l.parse(f.read())
    preparedTree = PrimitiveReplace().transform(commandtree)
    GraphVisitor().transform(preparedTree)
    nx.write_gexf(graph, "test.gexf")





fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.25)

axcolor = 'lightgoldenrodyellow'
axtime = plt.axes([0.25, 0.1, 0.65, 0.03], facecolor=axcolor)

commandCount = len(commandtree.children)
stime = Slider(axtime, 'Step', 0, commandCount, valinit=0)

def getNodeColor_activity(n):
    global lastActive
    start = n[1].get('laststart')
    end = n[1].get('lastend')

    input = n[1].get('inputadmission')
    # mark input for 11ms
    if input is not None and input + 1 * 1000 > lastActive:
        return 'r'

    if start is None:
        return 'g'
    if end is None:
        return 'y'
    # was it started more recently than it ended before?
    return 'y' if end < start else 'g'


def getNodeColor_time(n):
    global nodetimes
    id = n[1].get('id')
    return np.log2(np.median(nodetimes.get(id, [0])))
    #median_ms = [(nid, np.median(times) / 1000.0) for (nid, times) in nodetimes.items()]

def getNodeColor(n):
    if check.value_selected == 'color: activity':
        return getNodeColor_activity(n)
    else:
        return getNodeColor_time(n)

def update(val):
    global last_pos
    global lastCommand
    reset_()
    t = stime.val

    # evaluate for t steps
    GraphVisitor(executeCount = t).transform(preparedTree)
    print(lastCommand)



    #pos = nx.spring_layout(graph, k=0.7, pos=last_pos)
    pos = nx.circular_layout(graph, dim=2)
    #pos = nx.nx_pydot.graphviz_layout(graph, prog="osage")
    last_pos = pos

    # get nodes that currently execute
    colors = [getNodeColor(n) for n in graph.nodes(data=True)]

    ax.cla()
    # vmin/max
    nx.draw(graph, pos=pos, ax=ax, node_color=colors)
    nx.draw_networkx_labels(graph, pos=pos, ax=ax)
    fig.canvas.draw_idle()

stime.on_changed(update)

# button
prevax = plt.axes([0.7, 0.025, 0.1, 0.04])
btnPrev = Button(prevax, 'Prev', color=axcolor, hovercolor='0.975'),
def previous(event):
    t = stime.val
    t = max(0, t - 1)
    stime.set_val(t)

btnPrev[0].on_clicked(previous)

nextax = plt.axes([0.8, 0.025, 0.1, 0.04])
btnNext = Button(nextax, 'Next', color=axcolor, hovercolor='0.975'),
def next(event):
    t = stime.val
    t = min(commandCount, t + 1)
    stime.set_val(t)

btnNext[0].on_clicked(next)

## stats btn
statax = plt.axes([0.6, 0.025, 0.1, 0.04])
btnStats = Button(statax, 'Stats', color=axcolor, hovercolor='0.975'),
def stats(event):
    # get stats
    median_ms = [(nid, np.median(times) / 1000.0) for (nid, times) in nodetimes.items()]
    print([(get_name(nid), time) for (nid, time) in median_ms])

btnStats[0].on_clicked(stats)

# color activity or time
rax = plt.axes([0.05, 0.4, 0.1, 0.15])
check = RadioButtons(rax, ('color: activity', 'color: time'))
def check_fun(label):
    update(None)
    print([getNodeColor(n) for n in graph.nodes(data=True)])
check.on_clicked(check_fun)


# ## on click
# def onclick(e):
#     global last_pos
#     #MPL MouseEvent: xy=(549,14) xydata=(0.578125,0.10416666666666674) button=1 dblclick=False inaxes=Axes(0.8,0.025;0.1x0.04)
#     # get nearest node
#     ex, ey = e.xdata, e.ydata
#     dists = [(ex - x)*(ex - x)+(ey - y)*(ey - y) for x,y in last_pos]
#     closest_id = np.argmin(dists)
#     print(get_name(closest_id))
#
# fig.canvas.mpl_connect('button_press_event', onclick)


plt.show()

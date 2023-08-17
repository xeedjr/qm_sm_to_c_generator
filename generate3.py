#importing xmltodict module
from sys import setswitchinterval
import sys
import xmltodict
import uuid
import os
from pathlib import Path

def get_start():
    return """#pragma once

#include <array>

template <typename Event, typename StateData, typename Interface>
class MM {
public:

	StateData state_data;
	Interface *if_;

private:
	struct Status;

	enum InternalE {
		INITIAL,
		ENTRY,
		EXIT,
		EVENT,
		PARENT
	};
	enum StatusCode {
		NONE,
		HANDLED,
		UNHANDLED,
		IS_PARENT,
		TRAN,
	};

	typedef Status(*StateHandler)(MM*, InternalE , Event*);

	struct Status {
		StatusCode code;
		StateHandler state;
	};


	StateHandler current_state;
	std::array<StateHandler, 100> states_stack;

	Status tran(StateHandler handler) { Status s = { TRAN , handler };  return s; };
	Status handled() { Status s = { HANDLED , nullptr};  return s; };
	Status unhandled() { Status s = { UNHANDLED , nullptr };  return s; };
	Status parent(StateHandler handler) { Status s = { IS_PARENT , handler };  return s; };

public:
	MM(Interface* if_) {
		current_state = MM_top_;
		this->if_ = if_;
	};
	~MM() {};

	StateHandler get_LCA(StateHandler src, StateHandler dst) {
		do {
			src = get_parent_state(src);
			auto ldst = dst;
			do {
				ldst = get_parent_state(ldst);
				if (src == ldst) {
					return src;
				}
			} while (ldst != nullptr);
		} while (src != nullptr);

		return nullptr;
	};
	StateHandler get_parent_state(StateHandler state) {
		auto s = state(this, PARENT, nullptr);
		return s.state;
	};
	StateHandler get_initial_state(StateHandler state) {
		auto s = state(this, INITIAL, nullptr);
		return s.state;
	};

	StateHandler do_initial_transition(StateHandler src, StateHandler dst) {
		states_stack = { nullptr };
		StateHandler state = dst;
		int index = 0;
		states_stack[index++] = state;
		while ((state = get_parent_state(state)) != src) {
			states_stack[index++] = state;
		}
		for (int i = index - 1; i >= 0; i--) {
			states_stack[i](this, ENTRY, nullptr);
		}
		return states_stack[0];
	}

	StateHandler do_transition(StateHandler src, StateHandler dst) {
		states_stack = { nullptr };
		StateHandler state = dst;

		if (src == dst) {
			// reentry
			src(this, EXIT, nullptr);
			dst(this, ENTRY, nullptr);
			return dst;
		}
		
		auto lca_state = get_LCA(src, dst);

		// perform exits
		state = src;
		do {
			state(this, EXIT, nullptr);
			state = get_parent_state(state);
		} while (state != nullptr && state != lca_state);
		// perform entry
		int index = 0;
		states_stack[index++] = dst;
		while ((dst = get_parent_state(dst)) != lca_state) {
			states_stack[index++] = dst;
		}
		for (int i = index - 1; i >= 0; i--) {
			states_stack[i](this, ENTRY, nullptr);
		}
		state = states_stack[0];
		// perform initial trans
		StateHandler s;
		while ((s = get_initial_state(state)) != nullptr) {
			do_initial_transition(state, s);
			state = s;
		}

		return state;
	}

	void init() {
		// get initial transition target
		auto status = top_(INITIAL, nullptr);
		auto target_state = status.state;

		StateHandler finish_state = MM_top_;
		do {
			finish_state = do_initial_transition(finish_state, target_state);
		} while ((target_state = get_initial_state(finish_state)) != nullptr);

		current_state = finish_state;
	};

	void dispatch(Event* e) {
		Status status;
		StateHandler state;

		state = current_state;
		do {
			status = state(this, EVENT, e);
			state = get_parent_state(state);
		} while (status.code != HANDLED && status.code != TRAN && state != nullptr);

		if (status.code == TRAN) {
			current_state = do_transition(current_state, status.state);		
		}

	};
    """

def add_tab(str):
    str2 = ""
    for s in str.splitlines():
        str2 += "    " + s + '\n';
    return str2


def create_state_unique_name(state):
    name = ""
    i = state
    while True:
        name = i.name + "_" + name;
        if (i.parent == None):
            break;
        i = i.parent 
    return name

def generate_choice(tab, choice):
    str = ''
    is_else_guard = False;

    for c in choice:
        if hasattr(c, 'guard'):
            if c == choice[0]:
                str += tab + "if (" + c.guard + ") {\n"
            else:
                if c.guard != 'else':
                    str += tab + " else if (" + c.guard + ") {\n"
                else:
                    is_else_guard = True
                    str += tab + " else {\n"
        if hasattr(c, 'action'):
            str += tab + "    " + c.action + ";\n"
        if hasattr(c, 'target'):
            str += tab + "    status = tran(MM_" + create_state_unique_name(c.target) + ");\n"
        else:
            str += tab + "    status = handled();\n"
        #if 'choice' in c:
        #    str += generate_choice(tab+"    ", c.choice)
        str += tab + "}\n"
    if is_else_guard == False:
        str += tab + "else {\n"
        str += tab + "    status = unhandled();\n"
        str += tab + "}\n"
    
    return str

def generate_states(class_name, state):
    str = ''
    str += "static MM::Status MM_" + create_state_unique_name(state) + "(MM* thisp, MM::InternalE internal_e, Event* e) {\n"
    str += "    return thisp->" + create_state_unique_name(state) + "(internal_e, e);\n"
    str += "}\n"
    str += "\n"
    str += "Status " +  create_state_unique_name(state) + "(InternalE internal_e, Event* e) { \n"
    str += "    Status status = {NONE, nullptr};\n"
    str += "    switch(internal_e) {\n"
    for child in state.childs:
        if type(child) is Initial: 
            str += "    case INITIAL: {\n"
            if hasattr(child, 'action'):
                str += "        " + child.action + '\n'
            str += "        status = tran(&" + class_name + '_' + create_state_unique_name(child.target) + ');\n'
            str += "        break;\n"
            str += "    }\n"
    if hasattr(state, 'entry'):
        str += "    case ENTRY: {\n"
        str += "        " + state.entry + '\n'
        str += "        break;\n"
        str += "    }\n"
    if hasattr(state, 'exit'):
        str += "    case EXIT: {\n"
        str += "        " + state.exit + '\n'
        str += "        break;\n"
        str += "    }\n"


    str += "    case EVENT: {\n"
    str += "        switch(e->sig()) {\n"        

    for child in state.childs:
        if type(child) is Trans:  
            str += "        case Event::" + child.trig + ": {\n"
            if hasattr(child, 'action'):
                str += "           " + child.action + '\n'
            # process possible choice    
            if len(child.childs) > 0:
                str += generate_choice("              ", child.childs)
            else:
                if hasattr(child, 'target'):
                    str += "            status = tran(&" + class_name + '_' + create_state_unique_name(child.target) + ');\n'
            str += "        break;\n"
            str += "        }\n"

    str += "        default: {\n"
    str += "            status = unhandled();\n"
    str += "        }\n"
    str += "        }\n"
    str += "        break;\n"
    str += "    }\n"

    if hasattr(state, 'parent'):
        str += "    case PARENT: {\n"
        if state.parent != None:
            str += "        status = parent(&" + class_name + '_' + create_state_unique_name(state.parent) + ');\n'
        else:            
            str += "        status = parent(nullptr);\n"
        str += "        break;\n"
        str += "    }\n"
    str += "    }\n"
    str += "    return status;\n"
    str += "}\n"

    for child in state.childs:
        if type(child) is State:
            str += generate_states(class_name, child)

    return str


def link_targets_get_obj(child, target):
    p = child
    for dir in target.split('/'):
        if (dir == '..'):
            p = p.parent
        if (dir.isnumeric()):
            p = p.childs[int(dir)]
            
    return p
        
def link_targets(child):

    if hasattr(child, 'target'):
        child.target = link_targets_get_obj(child, child.target)
        pass

    for child in child.childs:
        link_targets(child)

    return child

class State:
    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

class Initial:
    def __init__(self, parent, name, target):
        self.parent = parent
        self.name = name
        self.target = target

class Choice:
    def __init__(self, parent):
        self.parent = parent

class Trans:
    def __init__(self, parent, trig):
        self.parent = parent
        self.trig = trig


def build_class(xml_obj, obj):
    obj.childs = []

    if '@target' in xml_obj:
        obj.target = xml_obj["@target"]
    if 'entry' in xml_obj:
        obj.entry = xml_obj["entry"]
    if 'exit' in xml_obj:
        obj.exit = xml_obj["exit"]
    if 'action' in xml_obj:
        obj.action = xml_obj["action"]
    if 'guard' in xml_obj:
        obj.guard = xml_obj["guard"]

    for k, v in list(xml_obj.items()):
        #print(k, v)

        if (k == 'initial'):
            obj.childs.append(build_class(v, Initial(obj, "initial", v['@target'])))
        if (k == 'tran'):
            vc = v
            if isinstance(vc, list) != True:
                vc = [vc]
            for c in vc:
                obj.childs.append(build_class(c, Trans(obj, c['@trig'])))    
        if (k == 'state'):
            vc = v
            if isinstance(vc, list) != True:
                vc = [vc]
            for c in vc:
                obj.childs.append(build_class(c, State(obj, c['@name'])))
        if (k == 'choice'):
            vc = v
            if isinstance(vc, list) != True:
                vc = [vc]
            for c in vc:
                obj.childs.append(build_class(c, Choice(obj)))

    return obj

def main():
    #converting xml to dictionary
    doc = dict();

    input_qm_file = Path(sys.argv[1])
    #input_qm_file = Path("QuadControlLoopQM.qm")

    with open(input_qm_file) as fd:
        doc = xmltodict.parse(fd.read())
    #print(doc)

    statechart = doc['model']['package']['class']['statechart'];

    o = build_class(statechart, State(None, 'top'))
    link_targets(o)

    class_name = input_qm_file.stem
    f = open(class_name + ".hpp", 'w+');
    ss = generate_states("MM", o)

    new = get_start() + "\n" + add_tab(ss) + "\n};"

    new = new.replace("MM", class_name)

    f.write(new)
    f.close()

    print("End");

if __name__ == "__main__":
    main()





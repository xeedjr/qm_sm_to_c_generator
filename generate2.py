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

def serahc_state(search_state, target_state):
    for dir in target_state.split('/'):
        if (dir == '..'):
            search_state = search_state['parent']
        if (dir.isnumeric()):
            s = search_state['state']
            if isinstance(s, list) != True:
                s = [s]
            if 'initial' in search_state:
                search_state = s[int(dir)-1]
            else:
                search_state = s[int(dir)]
    return search_state;

def list_states(dic): 
    for k, v in list(dic.items()):

        if k == '@target':
            dic['target_state'] = serahc_state(dic, v)
            del dic['@target']

        if isinstance(v, dict):
            if k != 'parent':
                list_states(v)
        if isinstance(v, list):
            for l in v:
                list_states(l)

def clear_dict(dic, parent = None):
    if parent == None:
        dic['@name'] = 'top';   
    dic['parent'] = parent;
    for k, v in list(dic.items()):
        if isinstance(v, dict):
            if k != 'parent':
                clear_dict(v, dic)
        if isinstance(v, list):
            for l in v:
                clear_dict(l, dic)
        if '@properties' == k:
            del dic['@properties']
        if 'choice_glyph' == k:
            del dic['choice_glyph']
        if 'tran_glyph' == k:
            del dic['tran_glyph']
        if 'state_glyph' == k:
            del dic['state_glyph']
        if 'initial_glyph' == k:
            del dic['initial_glyph']
        if 'state_diagram' == k:
            del dic['state_diagram']

def create_state_unique_name(state):
    name = ""
    i = state
    while True:
        name = i['@name'] + "_" + name;
        if (i['parent'] == None):
            break;
        i = i['parent']  
    return name

def generate_choice(tab, choice):
    str = ''
    is_else_guard = False;
    lc = choice
    if isinstance(lc, list) != True:
        lc = [lc]
    for c in lc:
        if 'guard' in c:
            if c == lc[0]:
                str += tab + "if (" + c['guard'] + ") {\n"
            else:
                if c['guard'] != 'else':
                    str += tab + " else if (" + c['guard'] + ") {\n"
                else:
                    is_else_guard = True
                    str += tab + " else {\n"
        if 'action' in c:
            str += tab + "    " + c['action'] + ";\n"
        if 'target_state' in c:
            str += tab + "    status = tran(MM_" + create_state_unique_name(c['target_state']) + ");\n"
        else:
            str += tab + "    status = handled();\n"
        if 'choice' in c:
            str += generate_choice(tab+"    ", c['choice'])
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
    if "initial" in state:
        str += "    case INITIAL: {\n"
        if 'action' in state['initial']:
            str += "        " + state['initial']['action'] + '\n'
        str += "        status = tran(&" + class_name + '_' + create_state_unique_name(state['initial']['target_state']) + ');\n'
        str += "        break;\n"
        str += "    }\n"
    if "entry" in state:
        str += "    case ENTRY: {\n"
        str += "        " + state['entry'] + '\n'
        str += "        break;\n"
        str += "    }\n"
    if "exit" in state:
        str += "    case EXIT: {\n"
        str += "        " + state['exit'] + '\n'
        str += "        break;\n"
        str += "    }\n"
    if "tran" in state:
        tran = state['tran']
        str += "    case EVENT: {\n"
        str += "        switch(e->sig()) {\n"        

        if isinstance(tran, list) != True:
            tran = [tran]

        for t in tran:
            str += "        case Event::" + t['@trig'] + ": {\n"
            if 'action' in t:
                str += "           " + t['action'] + '\n'
            if 'choice' in t:
                str += generate_choice("              ", t['choice'])
            else:
                if 'target_state' in t:
                    str += "            status = tran(&" + class_name + '_' + create_state_unique_name(t['target_state']) + ');\n'
            str += "        break;\n"
            str += "        }\n"

        str += "        default: {\n"
        str += "            status = unhandled();\n"
        str += "        }\n"
        str += "        }\n"
        str += "        break;\n"
        str += "    }\n"

    if 'parent' in state:
        str += "    case PARENT: {\n"
        if state['parent'] != None:
            str += "        status = parent(&" + class_name + '_' + create_state_unique_name(state['parent']) + ');\n'
        else:            
            str += "        status = parent(nullptr);\n"
        str += "        break;\n"
        str += "    }\n"
    str += "    }\n"
    str += "    return status;\n"
    str += "}\n"

    if 'state' in state:
        s = state['state']
        if isinstance(s, list) != True:
            s = [s]
        for i in s:
            str += generate_states(class_name, i)

    return str

def main():
    #converting xml to dictionary
    doc = dict();

    input_qm_file = Path(sys.argv[1])
    #input_qm_file = Path("BLQM.qm")

    with open(input_qm_file) as fd:
        doc = xmltodict.parse(fd.read())
    #print(doc)

    statechart = doc['model']['package']['class']['statechart'];

    clear_dict(statechart)
    list_states(statechart)

    #f = open("MM.h", 'r');
    #old = f.read()
    #f.close()
    class_name = input_qm_file.stem
    f = open(class_name + ".hpp", 'w+');
    ss = generate_states("MM", statechart)

    #index = old.find("// Start Generated2")
    #new = old[:(index + len('// Start Generated2') +1)]
    #new += add_tab(ss)
    #new += old[(index + len('// Start Generated2') +1):]
    new = get_start() + "\n" + add_tab(ss) + "\n};"

    new = new.replace("MM", class_name)

    f.write(new)
    f.close()

    print("End");

if __name__ == "__main__":
    main()





#pragma once

#include <array>

template <typename Event, typename StateData, typename Interface>
class BLQM {
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

	typedef Status(*StateHandler)(BLQM*, InternalE , Event*);

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
	BLQM(Interface* if_) {
		current_state = BLQM_top_;
		this->if_ = if_;
	};
	~BLQM() {};

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

		StateHandler finish_state = BLQM_top_;
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
    
    static BLQM::Status BLQM_top_(BLQM* thisp, BLQM::InternalE internal_e, Event* e) {
        return thisp->top_(internal_e, e);
    }
    
    Status top_(InternalE internal_e, Event* e) { 
        Status status = {NONE, nullptr};
        switch(internal_e) {
        case INITIAL: {
            if_->rf24_init();
            status = tran(&BLQM_top_Idle_);
            break;
        }
        case PARENT: {
            status = parent(nullptr);
            break;
        }
        }
        return status;
    }
    static BLQM::Status BLQM_top_Idle_(BLQM* thisp, BLQM::InternalE internal_e, Event* e) {
        return thisp->top_Idle_(internal_e, e);
    }
    
    Status top_Idle_(InternalE internal_e, Event* e) { 
        Status status = {NONE, nullptr};
        switch(internal_e) {
        case ENTRY: {
            if_->idle_enter();
            break;
        }
        case EXIT: {
            if_->idle_exit();
            break;
        }
        case EVENT: {
            switch(e->sig()) {
            case Event::CCS811_INT: {
               if_->read_temperature();
                status = tran(&BLQM_top_Idle_);
            break;
            }
            default: {
                status = unhandled();
            }
            }
            break;
        }
        case PARENT: {
            status = parent(&BLQM_top_);
            break;
        }
        }
        return status;
    }

};
# qm_sm_to_c_generator

Script generate2.py is designed to parse *.qm file and generate the state machine in *.hpp file.

The *.qm is designed in the QP tool https://www.state-machine.com/products/qm

# How generate state machine from qm file
Call python generate Filename.qm

# Limitation
1. Support only one state machine
2. Root class should be Blinky

# How script works
1. Import qp file (XML) into the dictionary
2. Clear dictionary from supporting fields
3. Build transition links between the states
4. Wal thrue the tree and generate all needed states
5. Write States with the State Machine engine into the file

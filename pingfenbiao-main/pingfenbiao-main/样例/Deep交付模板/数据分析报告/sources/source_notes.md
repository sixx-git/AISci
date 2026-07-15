\## Source List



Source ID: S1

Title: FedHybrid: Unifying Aggregation Strategies to Optimize Federated Learning on Non-IID Dataset

Type: paper

Identifier: DOI: 10.1016/j.procs.2025.04.570

Used For: R9, R24, R55



Source ID: S2

Title: Federated Learning with Non-IID Data

Type: paper

Identifier: arXiv:1806.00582

Used For: R6, R7, R8, R19, R20, R23, R31, R33, R45, R49



Source ID: S\_meta

Title: experiment\_metadata.md

Type: metadata

Identifier: experiment\_metadata.md (provided input file)

Used For: R1, R4, R5, R11, R12, R22, R32, R34, R36, R38, R39, R40, R41, R42, R43, R46, R47, R48, R49, R50, R51, R52, R53, R54, R55



Source ID: S\_dict

Title: datadict.md

Type: metadata

Identifier: datadict.md (provided input file)

Used For: R2, R3, R10, R29, R30, R35, R37, R44



Source ID: S\_data

Title: fl\_training\_metrics.csv

Type: dataset

Identifier: fl\_training\_metrics.csv (provided input file)

Used For: R13, R14, R15, R16, R17, R18, R21, R25, R26, R27, R28, R30, R31, R33, R34, R35, R36, R37, R38, R39, R40, R41, R42, R43, R44, R45, R46, R47, R48, R49, R50, R51, R52, R53, R54, R55



\## Rubric Map



Rubric ID: R1

Role: Standard (1 point)

Dimension: Information Acquisition

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Dataset: CIFAR-10 ... balanced 10 classes"



Rubric ID: R2

Role: Standard (1 point)

Dimension: Information Acquisition

Source ID: S\_dict

Location: datadict.md

Source Point: "Core variable definition" table contains Round, Alpha, Algorithm, Global\_Loss...



Rubric ID: R3

Role: Mandatory (2 points)

Dimension: Information Acquisition

Source ID: S\_dict

Location: datadict.md

Source Point: "α→0 means extreme heterogeneity; α→∞ means IID"



Rubric ID: R4

Role: Standard (1 point)

Dimension: Information Acquisition

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Systematic comparison of FedAvg and FedProx aggregation algorithms"



Rubric ID: R5

Role: Mandatory (2 points)

Dimension: Information Acquisition

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Hyperparameter: μ = 0.01 (empirically tuned)"



Rubric ID: R6

Role: Mandatory (2 points)

Dimension: Information Acquisition

Source ID: S2

Location: S2.pdf, Page 1

Source Point: "Other than the communication challenge, federated learning also faces the statistical challenge."



Rubric ID: R7

Role: Mandatory (2 points)

Dimension: Information Acquisition

Source ID: S2

Location: S2.pdf, Page 2

Source Point: "The IID sampling... is important to ensure that the stochastic gradient is an unbiased estimate of the full gradient."



Rubric ID: R8

Role: Mandatory (2 points)

Dimension: Information Acquisition

Source ID: S2

Location: S2.pdf, Page 1 (Abstract)

Source Point: "accuracy reduction can be explained by the weight divergence"



Rubric ID: R9

Role: Mandatory (2 points)

Dimension: Information Acquisition

Source ID: S1

Location: S1.pdf, Page 1 (Abstract)

Source Point: "combines the strengths of three existing methods: FedAvg, FedProx, and FedScaffold."



Rubric ID: R10

Role: Standard (1 point)

Dimension: Information Acquisition

Source ID: S\_dict

Location: datadict.md

Source Point: "Round: global communication round \[1, 100]"



Rubric ID: R11

Role: Mandatory (2 points)

Dimension: Information Acquisition

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Total clients 100 ... random sampling 10 per round (C=0.1)"



Rubric ID: R12

Role: Mandatory (2 points)

Dimension: Information Acquisition

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Local epochs: E=5"



Rubric ID: R13

Role: Critical (4 points)

Dimension: Scientific Reasoning

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Observe the starting round where Global\_Accuracy for Alpha=10, Algorithm=FedAvg stabilizes."



Rubric ID: R14

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Observe significant fluctuations in accuracy for Alpha=0.1 rows."



Rubric ID: R15

Role: Critical (4 points)

Dimension: Scientific Reasoning

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Compare Global\_Accuracy at round 100 across different Alpha groups."



Rubric ID: R16

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Compute mean Weight\_Divergence for different Alpha values."



Rubric ID: R17

Role: Critical (4 points)

Dimension: Scientific Reasoning

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Filter Alpha=0.5, compare final round accuracy for both algorithms."



Rubric ID: R18

Role: Critical (4 points)

Dimension: Scientific Reasoning

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Compare Weight\_Divergence values for FedProx vs FedAvg under the same Alpha."



Rubric ID: R19

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S2

Location: S2.pdf, Page 4

Source Point: "weight divergence... can be quantified by the earth mover's distance (EMD)"



Rubric ID: R20

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S2

Location: S2.pdf, Page 3 (Table 1)

Source Point: "accuracy... reduces significantly, by up to \~55% for neural networks trained for highly skewed non-IID data."



Rubric ID: R21

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Compare Client\_Variance between Alpha=0.1 and Alpha=10.0."



Rubric ID: R22

Role: Standard (1 point)

Dimension: Scientific Reasoning

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Model architecture: 5-Layer CNN"



Rubric ID: R23

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S2

Location: S2.pdf, Page 7 (Section 4.2)

Source Point: "accuracy can be increased by \~30% for the CIFAR-10 dataset with only 5% globally shared data."



Rubric ID: R24

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S1

Location: S1.pdf, Page 6 (Table 1)

Source Point: "obtained... 93.52% in CIFAR-10 datasets surpassing the other techniques."



Rubric ID: R25

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Observe performance differences between the two algorithms under high Alpha (mild heterogeneity)."



Rubric ID: R26

Role: Critical (4 points)

Dimension: Scientific Reasoning

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Based on CSV data, compute the number of rounds required to reach a specific accuracy threshold (e.g., 80%)."



Rubric ID: R27

Role: Standard (1 point)

Dimension: Scientific Reasoning

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Correlation analysis between Global\_Loss and Global\_Accuracy fields."



Rubric ID: R28

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Observe Weight\_Divergence changes during rounds 80-100."



Rubric ID: R29

Role: Standard (1 point)

Dimension: Scientific Reasoning

Source ID: S\_dict

Location: datadict.md

Source Point: "Range: \[0, 100]%"



Rubric ID: R30

Role: Standard (1 point)

Dimension: Scientific Reasoning

Source ID: S\_data / S\_dict

Location: fl\_training\_metrics.csv / datadict.md

Source Point: "Traverse CSV to check for missing values and physical constraint compliance."



Rubric ID: R31

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S2

Location: S2.pdf, Page 6 (Proposition 3.1)

Source Point: "This bound is affected by the learning rate, synchronization steps and gradients."



Rubric ID: R32

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Constraint on local update magnitude to suppress Client Drift"



Rubric ID: R33

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S2

Location: S2.pdf, Page 2 (Section 2.1)

Source Point: "1-class non-IID, where each client receives data partition from only a single class"



Rubric ID: R34

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Local optimization: min\[ F\_k(W) + (μ/2)‖W - W\_global‖² ]"



Rubric ID: R35

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S2

Location: S2.pdf, Page 4 (Section 3.1)

Source Point: "EMD between the distribution over classes on each device and the population distribution."



Rubric ID: R36

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "FedProx... theoretically more robust to Non-IID"



Rubric ID: R37

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S\_dict

Location: datadict.md

Source Point: "Reflects the dispersion degree of gradient directions among clients"



Rubric ID: R38

Role: Standard (1 point)

Dimension: Scientific Reasoning

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Alpha=10.0... ideal benchmark"



Rubric ID: R39

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Learning rate 0.01 ... constant, no decay"



Rubric ID: R40

Role: Standard (1 point)

Dimension: Scientific Reasoning

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Alpha=0.1: ... most clients have only 1-2 classes of samples"



Rubric ID: R41

Role: Standard (1 point)

Dimension: Scientific Reasoning

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Alpha=0.5: ... significant accuracy loss"



Rubric ID: R42

Role: Standard (1 point)

Dimension: Scientific Reasoning

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Batch Size = 32"



Rubric ID: R43

Role: Standard (1 point)

Dimension: Scientific Reasoning

Source ID: S\_meta

Location: experiment\_metadata.md

Source Point: "Optimizer: SGD ... with momentum (0.9)"



Rubric ID: R44

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S\_dict

Location: datadict.md

Source Point: "Each round involves: distribute model → local training → upload updates → global aggregation"



Rubric ID: R45

Role: Mandatory (2 points)

Dimension: Scientific Reasoning

Source ID: S2

Location: S2.pdf, Page 3 (Table 1)

Source Point: "accuracy... reduces significantly, up to 11% for MNIST"



Rubric ID: R46

Role: Mandatory (2 points)

Dimension: Report Synthesis

Source ID: S\_data / requirement

Location: fl\_training\_metrics.csv

Source Point: "Requirements document expects data visualization to support conclusions."



Rubric ID: R47

Role: Mandatory (2 points)

Dimension: Report Synthesis

Source ID: S\_data / requirement

Location: fl\_training\_metrics.csv

Source Point: "Requirements document expects quantitative analysis of Client Drift."



Rubric ID: R48

Role: Mandatory (2 points)

Dimension: Report Synthesis

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Core numerical values can be traced directly to original CSV records."



Rubric ID: R49

Role: Standard (1 point)

Dimension: Report Synthesis

Source ID: S\_meta, S\_dict, S\_data

Location: All input files

Source Point: "Refer to Excel template structure for logical organization."



Rubric ID: R50

Role: Standard (1 point)

Dimension: Report Synthesis

Source ID: S1, S2, S\_meta

Location: Multiple sources

Source Point: "Terms such as Non-IID, Client Drift, Weight Divergence, Proximal Term are used consistently."



Rubric ID: R51

Role: Standard (1 point)

Dimension: Report Synthesis

Source ID: S\_data / requirement

Location: fl\_training\_metrics.csv

Source Point: "Experimental design covers five Alpha levels (0.1, 0.5, 1.0, 5.0, 10.0)."



Rubric ID: R52

Role: Standard (1 point)

Dimension: Report Synthesis

Source ID: S\_data

Location: fl\_training\_metrics.csv

Source Point: "Final accuracy at Alpha=0.1 shows FedProx still faces significant challenges."



Rubric ID: R53

Role: Mandatory (2 points)

Dimension: Report Synthesis

Source ID: S1, S2

Location: S1.pdf, S2.pdf

Source Point: "Demand document requires strict source-to-claim alignment using \[S1] or \[S2] notation."



Rubric ID: R54

Role: Standard (1 point)

Dimension: Report Synthesis

Source ID: S\_meta, S\_dict, S\_data

Location: All input files

Source Point: "Report structure should include an executive summary with key data findings."



Rubric ID: R55

Role: Standard (1 point)

Dimension: Report Synthesis

Source ID: S1

Location: S1.pdf, Page 1 (Abstract)

Source Point: "utilizes... control variates from FedScaffold to minimize update variance."






Source ID: S1

Title:Backdoor Attacks and Defenses in Federated Learning: Survey, Challenges and Future Research Directions

Type: paper

Identifier: arXiv:2303.02213v1

Used For: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16, R17, R18, R19, R20, R21, R22, R23, R24, R25, R26, R27, R28, R29, R30, R31, R32, R33, R34, R35, R36, R37, R38, R39, R40, R41, R42, R43, R44, R45, R46, R47, R48, R49, R50



\## Source List



Source ID: S1

Title: Towards the Robustness of Differentially Private Federated Learning

Type: paper

Identifier: arXiv:2303.02213v1

Used For: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16, R17, R18, R19, R20, R21, R22, R23, R24, R25, R26, R27, R28, R29, R30, R31, R32, R33, R34, R35, R36, R37, R38, R39, R40, R41, R42, R43, R44, R45, R46, R47, R48, R49, R50



\## Rubric Map

\### Dimension: Information Acquisition



Rubric ID: R1

Role: Critical

Dimension: Information Acquisition

Source ID: S1

Location: Page 1, Abstract

Source Point: "...insertion of malicious functionality into a targeted model... cause the global model to misbehave on specific inputs while appearing normal in other cases."



Rubric ID: R2

Role: Mandatory

Dimension: Information Acquisition

Source ID: S1

Location: Page 4, Sec 2.1

Source Point: "Backdoor attacks can be categorized into two types: data poisoning and model poisoning."



Rubric ID: R3

Role: Mandatory

Dimension: Information Acquisition

Source ID: S1

Location: Page 12, Sec 3.2.1

Source Point: "The success of backdoor attacks is significantly influenced by the poisoning ratio, which refers to the proportion of poisoned data or malicious clients."



Rubric ID: R4

Role: Mandatory

Dimension: Information Acquisition

Source ID: S1

Location: Page 1, Abstract

Source Point: "...the heterogeneous distribution of data among clients in FL can make it difficult for the orchestration server to validate the integrity of local model updates."



Rubric ID: R5

Role: Standard

Dimension: Information Acquisition

Source ID: S1

Location: Page 12, Sec 3.2.2

Source Point: "Common datasets used for evaluating backdoor attacks in FL include MNIST, CIFAR-10, and TinyImageNet."



Rubric ID: R6

Role: Mandatory

Dimension: Information Acquisition

Source ID: S1

Location: Page 11, Sec 3.1.2

Source Point: "The attacker can use a scaling factor to amplify the poisoned update, effectively replacing the global model with the backdoored one (Model Replacement Attack)."



Rubric ID: R7

Role: Standard

Dimension: Information Acquisition

Source ID: S1

Location: Page 10, Sec 3.1.2

Source Point: "In DBA, the global trigger is decomposed into several local triggers, which are then embedded into the local models of different malicious clients."



Rubric ID: R8

Role: Mandatory

Dimension: Information Acquisition

Source ID: S1

Location: Page 9, Sec 3.1.1

Source Point: "Stealthiness is a crucial requirement for backdoor attacks to bypass the anomaly detection mechanisms at the server."



Rubric ID: R9

Role: Standard

Dimension: Information Acquisition

Source ID: S1

Location: Page 25, Sec 4.4

Source Point: "Backdoor attacks can target either the generic global model or specific personalized models in PFL."



Rubric ID: R10

Role: Mandatory

Dimension: Information Acquisition

Source ID: S1

Location: Page 11, Sec 3.1.3

Source Point: "Adaptive attackers can monitor the defense strategy of the server and adjust their poisoning behavior to remain undetected."



Rubric ID: R11

Role: Standard

Dimension: Information Acquisition

Source ID: S1

Location: Page 10, Sec 3.1.2

Source Point: "...triggers can be categorized into digital triggers (e.g., fixed patterns) and semantic triggers (e.g., specific features of an object)."



Rubric ID: R12

Role: Critical

Dimension: Information Acquisition

Source ID: S1

Location: Page 28, Sec 5.2

Source Point: "A key challenge for attackers is the durability of the backdoor, as it may be erased or forgotten during the aggregation process in subsequent rounds."



\### Dimension: Scientific Reasoning



Rubric ID: R13

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 16, Sec 4.1.1

Source Point: "Robust aggregators like Krum or Median can be bypassed by attackers who constrain their poisoned updates within the range of benign updates."



Rubric ID: R14

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 20, Sec 4.2.1

Source Point: "DP-based defenses add Gaussian or Laplacian noise to the aggregated updates to mitigate the influence of any single client, including malicious ones."



Rubric ID: R15

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 18, Sec 4.1.3

Source Point: "Pruning techniques aim to identify and remove 'dormant' or 'backdoor' neurons that are only activated by the trigger pattern."



Rubric ID: R16

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 29, Sec 5.3

Source Point: "However, excessive pruning or noise injection can lead to a significant drop in the main task accuracy (utility-security trade-off)."



Rubric ID: R17

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 19, Sec 4.1.4

Source Point: "Adversarial training is computationally expensive for resource-constrained FL clients as it requires generating adversarial examples during local training."



Rubric ID: R18

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 18, Sec 4.1.3

Source Point: "Trigger inversion methods attempt to reconstruct the potential trigger by optimizing an input that causes a specific classification error."



Rubric ID: R19

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 21, Sec 4.2.3

Source Point: "Knowledge distillation can be used to transfer the knowledge from a potentially poisoned model to a clean student model using a small set of clean data."



Rubric ID: R20

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 25, Sec 4.4

Source Point: "In personalized FL, it is scientifically difficult to distinguish between legitimate local features (due to Non-IID) and malicious backdoor features."



Rubric ID: R21

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 27, Sec 5.1

Source Point: "Most server-side defenses assume the existence of a clean proxy dataset, which is often unavailable in real-world privacy-preserving FL."



Rubric ID: R22

Role: Standard

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 11, Sec 3.1.2

Source Point: "To bypass L2-norm-based anomaly detection, attackers use a constraint-and-scale method to keep the norm of the scaled update within a 'benign' threshold."



Rubric ID: R23

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 17, Sec 4.1.2

Source Point: "Feature squeezing reduces the search space for triggers by decreasing the color bit depth or applying smoothing filters to inputs."



Rubric ID: R24

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 16, Sec 4.1.1

Source Point: "Clustering-based defenses may misclassify honest updates as malicious in highly non-IID scenarios where benign updates form multiple diverse clusters."



Rubric ID: R25

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 30, Sec 6

Source Point: "Future defenses should dynamically adjust their filtering thresholds to adapt to the changing distribution of client updates and attack intensities."



Rubric ID: R26

Role: Standard

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 12, Sec 3.2.1

Source Point: "The attack success rate does not always increase linearly with the number of clients; it depends on the aggregation rule and the total population size."



Rubric ID: R27

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 31, Sec 6

Source Point: "Model watermarking for IP protection shares the same underlying mechanism as backdoor attacks, using hidden triggers to verify ownership."



Rubric ID: R28

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 11, Sec 3.1.2

Source Point: "The attacker solves a constrained optimization problem: L = L\_class + λ L\_dist, where L\_dist forces the update to be close to the previous global model."



Rubric ID: R29

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 15, Sec 4

Source Point: "Defenses can be applied during the training process (e.g., robust aggregation) or after training (e.g., model fine-pruning)."



Rubric ID: R30

Role: Standard

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 15, Sec 4.1

Source Point: "FedAvg is highly vulnerable because a single malicious update with a large norm can significantly bias the global model toward the backdoor goal."



Rubric ID: R31

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 17, Sec 4.1.2

Source Point: "Shapley value-based methods provide a principled way to quantify the contribution of each client to the model's performance and identify outliers."



Rubric ID: R32

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 26, Sec 5

Source Point: "When secure aggregation (e.g., HE) is used, the server can only see the sum of updates, making it impossible to audit individual updates for backdoors."



Rubric ID: R33

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 28, Sec 5.3

Source Point: "Complex defense algorithms incur significant energy and memory overhead, which may not be feasible for battery-powered edge devices."



Rubric ID: R34

Role: Standard

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 30, Sec 6

Source Point: "Neural Architecture Search (NAS) can be explored to automatically design model architectures that are inherently more resistant to trigger activation."



Rubric ID: R35

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 19, Sec 4.1.4

Source Point: "Detectors designed for adversarial examples (evasion attacks) can sometimes be repurposed to identify backdoor triggers during inference."



Rubric ID: R36

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 26, Sec 4.5

Source Point: "In Vertical FL (VFL), the attack surface is different because clients hold different features rather than different samples, complicating trigger design."



Rubric ID: R37

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 16, Sec 4.1.1

Source Point: "Filtering malicious updates by clustering them based on cosine similarity before the final aggregation step can improve robustness."



Rubric ID: R38

Role: Standard

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 28, Sec 5.2

Source Point: "Defenses must consider the temporal aspect of attacks, as some backdoors require multiple rounds of consistent poisoning to become persistent."



Rubric ID: R39

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 4, Sec 2.1

Source Point: "Backdoor attacks are more targeted than label-flipping attacks; the former only misclassifies specific inputs with triggers, while the latter affects entire classes."



Rubric ID: R40

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 22, Sec 4.3

Source Point: "Certified robustness provides formal guarantees but often suffers from loose bounds and limited scalability to large-scale deep neural networks."



\### Dimension: Report Synthesis



Rubric ID: R41

Role: Standard

Dimension: Report Synthesis

Source ID: S1

Location: Page 13, Table 2

Source Point: "Table 2 and Table 3 summarize existing attack and defense methods with publication years."



Rubric ID: R42

Role: Standard

Dimension: Report Synthesis

Source ID: S1

Location: Entire Paper

Source Point: "The paper structure (Intro -> Attacks -> Defenses -> Challenges) is the standard paradigm for such survey reports."



Rubric ID: R43

Role: Standard

Dimension: Report Synthesis

Source ID: S1

Location: Page 30, Sec 6

Source Point: "The Future Directions section mentions the need to explore backdoor security in LLMs and complex tasks."



Rubric ID: R44

Role: Standard

Dimension: Report Synthesis

Source ID: S1

Location: Page 1-3

Source Point: "The paper logic proceeds from FL vulnerabilities to attacks, then to defenses targeting attack characteristics."



Rubric ID: R45

Role: Standard

Dimension: Report Synthesis

Source ID: S1

Location: Page 5, Fig 2

Source Point: "The paper provides a hierarchical taxonomy diagram (Figure 2) for defense methods."



Rubric ID: R46

Role: Standard

Dimension: Report Synthesis

Source ID: S1

Location: Page 28, Sec 5.3

Source Point: "The paper specifically discusses the trade-off between communication/computation efficiency and security defenses."



Rubric ID: R47

Role: Standard

Dimension: Report Synthesis

Source ID: S1

Location: Page 27-31

Source Point: "The 'Future Challenges' section indicates research trends for later years (e.g., adaptive defenses, privacy-preserving aggregation)."



Rubric ID: R48

Role: Standard

Dimension: Report Synthesis

Source ID: S1

Location: Page 30-31, Sec 6

Source Point: "The paper proposes 4-5 clear future research directions (e.g., interpretability, defenses in heterogeneous environments)."



Rubric ID: R49

Role: Standard

Dimension: Report Synthesis

Source ID: S1

Location: Page 12, Sec 3.2.1

Source Point: "The paper emphasizes Non-IID as a core variable that must be considered in all FL security evaluations."



Rubric ID: R50

Role: Standard

Dimension: Report Synthesis

Source ID: S1

Location: Page 31, Conclusion

Source Point: "The conclusion explicitly states that there is no single 'silver bullet' defense; multi-layer defense collaboration is needed."


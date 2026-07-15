\## Source List



Source ID: S1

Title: Towards the Robustness of Differentially Private Federated Learning

Type: paper

Identifier: DOI: 10.1609/aaai.v38i18.29967

Used For: R1, R2, R7, R8, R16, R17, R21, R24, R26, R32, R33, R40, R42, R44, R48, R49



Source ID: S2

Title: DP-BREM: Differentially-Private and Byzantine-Robust Federated Learning with Client Momentum

Type: paper

Identifier: arXiv:2306.12608

Used For: R9, R11, R13, R18, R19, R27, R28, R30, R31, R36, R39, R45



Source ID: S3

Title: Can You Really Backdoor Federated Learning?

Type: paper

Identifier: arXiv:1911.07963

Used For: R3, R4, R6, R10, R12, R14, R15, R20, R22, R23, R25, R34, R35, R37, R38, R43



\## Rubric Map



Rubric ID: R1

Role: Mandatory

Dimension: Information Acquisition

Source ID: S1

Location: Page 1

Source Point: "Existing FL works usually secure data privacy by perturbing local model gradients via the differential privacy (DP) technique."



Rubric ID: R2

Role: Critical

Dimension: Information Acquisition

Source ID: S1

Location: Page 1

Source Point: "...DP-FL frameworks are not inherently robust and are vulnerable to a carefully-designed attack method."



Rubric ID: R3

Role: Mandatory

Dimension: Information Acquisition

Source ID: S3

Location: Page 1

Source Point: "...the EMNIST dataset, a real-life, user-partitioned, and non-iid dataset."



Rubric ID: R4

Role: Mandatory

Dimension: Information Acquisition

Source ID: S3

Location: Page 1

Source Point: "...we show that norm clipping and 'weak' differential privacy mitigate the attacks..."



Rubric ID: R5

Role: Standard

Dimension: Information Acquisition

Source ID: N/A

Location: N/A

Source Point: Task requirement (time range 2018–2025)



Rubric ID: R6

Role: Mandatory

Dimension: Information Acquisition

Source ID: S3

Location: Figure 5 (Page 10)

Source Point: Shows backdoor task accuracy changes under different privacy budget ε values.



Rubric ID: R7

Role: Critical

Dimension: Information Acquisition

Source ID: S1

Location: Page 3

Source Point: "The adversary is assumed to know the DP parameters and the aggregation rule."



Rubric ID: R8

Role: Standard

Dimension: Information Acquisition

Source ID: S1

Location: Page 1

Source Point: "...defend against poisoning attacks by filtering the local gradients..."



Rubric ID: R9

Role: Standard

Dimension: Information Acquisition

Source ID: S2

Location: Page 1

Source Point: "...focus on simultaneously achieving differential privacy (DP) and Byzantine robustness..."



Rubric ID: R10

Role: Mandatory

Dimension: Information Acquisition

Source ID: S3

Location: Page 6

Source Point: "...the success of the attack largely depends on the fraction of adversaries..."



Rubric ID: R11

Role: Critical

Dimension: Information Acquisition

Source ID: S2

Location: Page 1

Source Point: "...exposing the small malicious perturbations... that are undetectable in a single round but accumulate over time."



Rubric ID: R12

Role: Standard

Dimension: Information Acquisition

Source ID: S3

Location: Page 1

Source Point: "...study of backdoor attacks and defenses for the EMNIST dataset."



Rubric ID: R13

Role: Mandatory

Dimension: Information Acquisition

Source ID: S2

Location: Page 25

Source Point: "However, these works only ensure the security of the aggregation step and do not achieve DP..."



Rubric ID: R14

Role: Standard

Dimension: Information Acquisition

Source ID: S3

Location: Figure 5 (Page 10)

Source Point: "(c) Attack frequency = 1/5... (a) Attack frequency = 1/3"



Rubric ID: R15

Role: Mandatory

Dimension: Information Acquisition

Source ID: S3

Location: Page 1

Source Point: "...the goal of the adversary is to reduce the performance... while maintaining a good performance on the main task."



Rubric ID: R16

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 1

Source Point: "...we unveil that although DP noisy perturbation can improve the learning robustness, DP-FL frameworks are not inherently robust..."



Rubric ID: R17

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 1

Source Point: "...how to secure federated learning in both privacy and robustness still needs further exploration."



Rubric ID: R18

Role: Critical

Dimension: Scientific Reasoning

Source ID: S2

Location: Page 1

Source Point: "...random noise... and the selected central gradients inevitably incorporate a higher proportion of poisoned gradients."



Rubric ID: R19

Role: Critical

Dimension: Scientific Reasoning

Source ID: S2

Location: Page 1

Source Point: "The robustness is achieved via client momentum... exposing the small malicious perturbations..."



Rubric ID: R20

Role: Critical

Dimension: Scientific Reasoning

Source ID: S3

Location: Page 1

Source Point: "...norm clipping and 'weak' differential privacy mitigate the attacks without hurting the overall performance."



Rubric ID: R21

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 3

Source Point: "The adversary aims to design local gradients... to bypass both the DP noise and the robust aggregator."



Rubric ID: R22

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S3

Location: Page 1

Source Point: "...without hurting the overall performance." (implies trade-off; complete defense would hurt utility)



Rubric ID: R23

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S3

Location: Page 1

Source Point: "...the performance of the attack largely depends on the fraction of adversaries present."



Rubric ID: R24

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 1

Source Point: Points out the complex interplay of robustness and privacy under Non-IID.



Rubric ID: R25

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S3

Location: Page 4

Source Point: "In order to bound the sensitivity of each user’s update, we clip the L2 norm of the update."



Rubric ID: R26

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Abstract / Page 1

Source Point: "...vulnerable to a carefully-designed attack method."



Rubric ID: R27

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S2

Location: Page 1

Source Point: "...reducing the variance of the honest clients and exposing... malicious perturbations."



Rubric ID: R28

Role: Standard

Dimension: Scientific Reasoning

Source ID: S2

Location: Page 25

Source Point: "However, these works only ensure the security of the aggregation step and do not achieve DP..."



Rubric ID: R29

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: References (Xie et al. 2022)

Source Point: "Uncovering the Connection Between Differential Privacy and Certified Robustness"



Rubric ID: R30

Role: Critical

Dimension: Scientific Reasoning

Source ID: S2

Location: Page 1

Source Point: "...undetectable in a single round but accumulate over time."



Rubric ID: R31

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S2

Location: Page 25

Source Point: Discusses comparison of median, Krum, Bulyan rules.



Rubric ID: R32

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 1

Source Point: "...perturbing local model gradients... before aggregation."



Rubric ID: R33

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Abstract / Page 1

Source Point: "DP noisy perturbation can improve... but DP-FL frameworks are not inherently robust."



Rubric ID: R34

Role: Standard

Dimension: Scientific Reasoning

Source ID: S3

Location: Page 1

Source Point: "...the 'complexity' of the targeted task."



Rubric ID: R35

Role: Critical

Dimension: Scientific Reasoning

Source ID: S3

Location: Abstract / Page 1

Source Point: Uses the word "mitigate" rather than "complete defense".



Rubric ID: R36

Role: Standard

Dimension: Scientific Reasoning

Source ID: S2

Location: Page 1

Source Point: "...focus on... cross-silo FL."



Rubric ID: R37

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S3

Location: Page 6

Source Point: "...performance of the attack largely depends on the fraction of adversaries."



Rubric ID: R38

Role: Mandatory

Dimension: Scientific Reasoning

Source ID: S3

Location: Figure 5 (Page 10)

Source Point: Shows suppression of backdoor accuracy under small ε.



Rubric ID: R39

Role: Critical

Dimension: Scientific Reasoning

Source ID: S2

Location: Page 25

Source Point: "...play with median statistics of gradient contributions."



Rubric ID: R40

Role: Critical

Dimension: Scientific Reasoning

Source ID: S1

Location: Page 1

Source Point: "...still needs further exploration."



Rubric ID: R41

Role: Mandatory

Dimension: Report Synthesis

Source ID: N/A

Location: N/A

Source Point: Task requirement (structured evidence table)



Rubric ID: R42

Role: Mandatory

Dimension: Report Synthesis

Source ID: S1

Location: Page 1

Source Point: Conclusion that DP-FL is not inherently robust.



Rubric ID: R43

Role: Standard

Dimension: Report Synthesis

Source ID: S3

Location: Abstract / Page 1

Source Point: Uses "mitigate" instead of "complete defense".



Rubric ID: R44

Role: Standard

Dimension: Report Synthesis

Source ID: S1

Location: Page 1

Source Point: "...how to secure federated learning in both privacy and robustness still needs further exploration."



Rubric ID: R45

Role: Standard

Dimension: Report Synthesis

Source ID: S2

Location: Page 25

Source Point: Privacy prevents model auditing.



Rubric ID: R46

Role: Mandatory

Dimension: Report Synthesis

Source ID: N/A

Location: N/A

Source Point: General language quality expectation.



Rubric ID: R47

Role: Standard

Dimension: Report Synthesis

Source ID: N/A

Location: N/A

Source Point: Expectation to emphasize recency (AAAI-24).



Rubric ID: R48

Role: Mandatory

Dimension: Report Synthesis

Source ID: S1

Location: Page 1

Source Point: Discusses Non-IID as source of vulnerability.



Rubric ID: R49

Role: Standard

Dimension: Report Synthesis

Source ID: S1

Location: Abstract / Page 1

Source Point: New attack method as counterexample.



Rubric ID: R50

Role: Standard

Dimension: Report Synthesis

Source ID: N/A

Location: N/A

Source Point: Task requirement (confidence score).


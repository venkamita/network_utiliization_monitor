# SDN Mininet Network Utilization Monitor

## 📌 Objective
To monitor network traffic using SDN by collecting real-time port statistics from OpenFlow switches using a Ryu controller.

---

## 🧠 Concept
This project demonstrates:
- SDN architecture (Controller + Switch)
- Flow rule behavior
- Network monitoring using OpenFlow statistics

---

## 🏗️ Topology
Single switch topology with 3 hosts:
h1 --- s1 --- h2
         |
        h3

---

## ⚙️ Setup

Install dependencies:
```bash
sudo apt update
sudo apt install mininet python3-ryu iperf

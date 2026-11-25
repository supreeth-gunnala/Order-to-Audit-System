# 8-MINUTE VIDEO DEMONSTRATION WALKTHROUGH SCRIPT
## NIT Trichy Internship Challenge: Order-to-Audit System

**Target Video Duration:** 7:30 to 8:00 minutes  
**Presenter Tone:** Professional, confident, engineering-focused  
**Target Audience:** Technical Evaluation Committee, Factory Owner & Auditors

---

### [00:00 – 01:00] Scene 1: Introduction & Technology Choices
- **Screen:** Show application landing page / login screen (`http://localhost:8000/login/`).
- **Narrator Script:**
  > "Hello, this is my submission for the NIT Trichy Order-to-Audit System for small-scale food manufacturing. 
  > To meet the rigorous demands of real manufacturing accounting, this system is built with Python 3.11, Django 5.2, PostgreSQL 18, Bootstrap 5, HTMX, and ReportLab. 
  > We use arbitrary-precision Decimal arithmetic for all currency and inventory calculations, ensuring zero floating-point errors. 
  > The database maintains an immutable StockLedger, weighted-average material valuation, and complete GST compliance."

---

### [01:00 – 02:00] Scene 2: Benchmark Reset & Seed State Verification
- **Screen:** Terminal running `python manage.py run_benchmark_scenario --reset`, then opening Owner Dashboard (`http://localhost:8000/dashboard/owner/`).
- **Narrator Script:**
  > "We execute the reproducible scenario runner. Notice that all initial conditions are loaded:
  > Flour: 100 kg at ₹42, Cooking Oil: 30 L at ₹140, Spice Mix: 5 kg at ₹200, Pouches: 500 pieces at ₹2.50, Cartons: 30 pieces at ₹15, and Finished Murukku: 50 packets.
  > On the Owner Dashboard, all numbers are live database aggregates. There are no hardcoded cards or dummy stats."

---

### [02:00 – 03:15] Scene 3: Raw Material Purchase & Production Run Execution
- **Screen:** Inward Purchase screen (`/inventory/purchases/new/`), then Production Run execution (`/production/runs/new/`).
- **Narrator Script:**
  > "Step 1: We receive 60 kg of flour at ₹45/kg from our vendor. The system calculates the new Weighted-Average Cost: 100 kg at ₹42 plus 60 kg at ₹45 equals ₹43.1250 per kg across 160 kg.
  > Step 2: The Production Supervisor launches a Murukku 200g run using BOM v1.
  > We issue 40 kg flour, 10.5 litres of oil, and 1.2 kg spice mix. Output recorded is 188 good packets, 6 damaged pouches, and 9 outer cartons.
  > Direct labour is ₹1,200 and gas/power is ₹600.
  > Upon submission, notice two critical alerts:
  > First, Oil consumption variance is positive 5.00%, which exceeds the 3% tolerance.
  > Second, Yield variance is negative 6.00%, flagged because 188 packets were produced instead of 200.
  > Third, our packaging capacity check warns that 9 cartons hold only 180 packets at 20 packets per carton, leaving 8 packets unboxed.
  > The closing inventory balances reconcile perfectly: Flour at 120 kg, Oil at 19.5 L, Pouches at 306 pcs, Cartons at 21 pcs, and Finished Goods increased to 238 packets."

---

### [03:15 – 04:30] Scene 4: Mobile Salesman View & Order Entry
- **Screen:** Switch browser to responsive mobile device simulation (375px width) and log in as `salesman_a`.
- **Narrator Script:**
  > "Now switching to our mobile salesman interface.
  > Salesman A logs in on his smartphone. He sees only his assigned customers on the Trichy route.
  > He selects Retailer A in Tamil Nadu and adds Murukku 200g.
  > The system automatically retrieves the pre-tax selling price of ₹50 per packet.
  > He enters 150 packets. The interface calculates the subtotal of ₹7,500, estimated 5% GST of ₹375, and order total of ₹7,875 in real time.
  > He taps Submit Order. The order is committed to the database with status 'Submitted'."

---

### [04:30 – 05:45] Scene 5: Admin Verification, GST Invoicing & Dispatch
- **Screen:** Desktop view logged in as `factory_admin`. Open Order detail (`/sales/orders/1/`).
- **Narrator Script:**
  > "The Factory Admin opens the incoming order.
  > The admin verifies customer tax jurisdiction, price, and checks finished stock. The stock check shows 238 packets available—sufficient for 150 packets.
  > The admin approves the order and clicks 'Generate GST Tax Invoice'.
  > Because Retailer A is in Tamil Nadu and our factory is in Tamil Nadu, this is an intra-state supply. The system applies CGST 2.5% (₹187.50) and SGST 2.5% (₹187.50), totaling ₹7,875.00.
  > We can click 'Download PDF' to inspect the official GST Rule 46 compliant Tax Invoice generated via ReportLab.
  > Next, Admin records dispatch. 150 packets are dispatched, automatically reducing Finished Goods stock from 238 to exactly 88 packets."

---

### [05:45 – 06:45] Scene 6: Stock Shortage Protection (Distributor B) & Payment Receipt
- **Screen:** Salesman B order detail (`/sales/orders/2/`) and Payment Entry (`/sales/payments/new/`).
- **Narrator Script:**
  > "Next, Salesman B submits an order for Distributor B in Karnataka for 120 packets.
  > Notice the stock warning: requested 120 packets, available in finished stock only 88 packets, shortage of 32 packets.
  > If the Admin attempts to dispatch this order, the database-level check immediately blocks it: 'Insufficient stock. Invalid dispatch blocked to prevent negative inventory.'
  > For payment: Retailer A pays ₹4,000 via bank transfer. We record the receipt. The invoice outstanding balance automatically reduces from ₹7,875 to ₹3,875."

---

### [06:45 – 07:30] Scene 7: Auditor Reports & Production Costing
- **Screen:** Auditor Dashboard (`/reports/dashboard/`) and GSTR-1 (`/reports/gst-outward/`).
- **Narrator Script:**
  > "We now log in as the Auditor in read-only mode.
  > We review the Production Costing report: Total batch cost is ₹5,855 (materials ₹4,055 + labour ₹1,200 + overhead ₹600).
  > Cost per good packet is exactly ₹31.14.
  > In the GSTR-1 summary, outward supplies reflect ₹7,500 taxable value with ₹187.50 CGST and ₹187.50 SGST.
  > In Receivables Ageing, Retailer A's balance of ₹3,875 is tracked under the 0–30 days bracket.
  > Every report can be exported in one click to CSV, Excel, or PDF."

---

### [07:30 – 08:00] Scene 8: Conclusion & Acceptance Verification
- **Screen:** Terminal showing `python manage.py test` passing 8/8 suites.
- **Narrator Script:**
  > "Our automated test suite runs 8 comprehensive test cases validating all 19 prompt acceptance criteria A through S.
  > The system runs completely without containers on local PostgreSQL, providing full auditability, data integrity, and production-grade reliability. Thank you!"

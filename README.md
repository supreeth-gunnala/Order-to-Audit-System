# Order-to-Audit ERP System for Packaged Food Manufacturing
### NIT Trichy Internship Challenge Prototype & Benchmark Implementation

---

## 1. Project Overview
This project is an enterprise-grade **Order-to-Audit Management System** specifically designed for a small-to-medium packaged-food manufacturing enterprise producing traditional South Indian snacks (Murukku, Mixture, Chips, and Sweets). 

The system unifies the entire business lifecycle into a single traceable database architecture:
- **Sales Route & Ordering**: Salesman mobile ordering, admin review, and verification.
- **GST Tax Compliance**: Sequential Rule 46 invoices with accurate intra-state (CGST+SGST) vs inter-state (IGST) taxation.
- **Recipe & Batch Production**: Versioned Bill of Materials (BOM), actual ingredient consumption, yield variance alerting, packaging reconciliation, and overhead absorption.
- **Perpetual Inventory Ledger**: Double-entry style stock ledger tracking every receipt, issue, dispatch, and scrap movement without negative inventory.
- **Cost Accounting & Audit**: Weighted-Average Costing (WAC), cost-per-good-packet calculation, statutory management tax summaries (GSTR-1, GSTR-3B), receivables aging, and PDF/Excel/CSV exports.

---

## 2. Problem Being Solved
Small food manufacturers often struggle with decoupled operations: salesmen take orders via WhatsApp, production supervisors estimate ingredient consumption informally, invoices are created manually with tax errors, and inventory variances go unnoticed until year-end audits. 

This system solves these issues by:
1. Connecting BOM recipes directly to real-time ingredient deductions.
2. Flagging production yield variances and material over-consumption exceeding configurable tolerances (default 3%).
3. Enforcing physical packaging capacity validation (e.g., carton capacity vs good output).
4. Preventing dispatch and overselling when finished-goods inventory is insufficient.
5. Providing an immutable audit trail and preventing silent deletions of posted invoices.

---

## 3. Technology Stack
- **Backend Framework**: Python 3.11, Django 5.2.19, Django REST Framework
- **Primary Database**: PostgreSQL 18 (with `psycopg` 3.2.1)
- **Frontend & UI**: HTML5, CSS3, JavaScript, Bootstrap 5.3, Bootstrap Icons, Chart.js 4.4
- **Financial Arithmetic**: Python `Decimal` (zero binary floating-point rounding errors)
- **Document Generation**: ReportLab 5.0 (for GST Tax Invoice and Audit PDFs)
- **Data Exports**: OpenPyXL 3.1.5 (Excel `.xlsx`) and standard CSV engine
- **Environment Management**: Python virtual environments (`venv`) and `python-dotenv`

---

## 4. Why This Stack Was Selected
- **Python & Django**: Django provides a battle-tested ORM with native transaction management (`transaction.atomic`), row-level locking (`select_for_update`), and built-in CSRF/authentication security ideal for financial systems.
- **PostgreSQL**: PostgreSQL offers strict relational constraints, ACID compliance, and concurrency controls necessary for perpetual inventory accounting.
- **Bootstrap 5 & Mobile-First Design**: Salesmen in the field operate on mobile devices, while factory owners and accountants require comprehensive desktop dashboards. Bootstrap 5 easily supports both paradigms with a unified design system.
- **Decimal & ReportLab**: Eliminates financial rounding inaccuracies and delivers pixel-perfect, printable GST invoices compliant with statutory standards.

---

## 5. System Architecture
The application uses Domain-Driven Design (DDD) split into six decoupled apps:
- `apps.core`: Custom User model, Role-Based Access Control (RBAC), context processors, and immutable `AuditLog`.
- `apps.master_data`: Product catalog, customer & distributor profiles, supplier master, and centralized unit conversion service.
- `apps.inventory`: Perpetual inventory items, `StockLedger`, purchase receipts, and Weighted-Average Costing.
- `apps.production`: Bill of Materials (BOM), `ProductionRun` execution, variance analysis engine, and product costing.
- `apps.sales`: Sales orders, GST invoice generation, finished goods dispatch, and customer payment allocations.
- `apps.reports`: Statutory GST summaries (GSTR-1, GSTR-3B), production costing sheets, receivables aging, and export engines.

```
Order-to-Audit System/
├── apps/
│   ├── core/                  # RBAC, User model, Audit Trail, Dashboard
│   ├── master_data/           # Products, Customers, Suppliers, UOM Conversions
│   ├── inventory/             # Items, Purchases, StockLedger, WAC Engine
│   ├── production/            # BOMs, Batch Runs, Yield & Oil Variances, Costing
│   ├── sales/                 # Orders, GST Invoices, Dispatches, Payments, PDF
│   └── reports/               # GSTR-1, GSTR-3B, Costing, Aging, Exporters
├── config/                    # Django project configuration & settings
├── templates/                 # Premium responsive Bootstrap 5 templates
├── static/                    # CSS & JS assets
├── requirements.txt           # Python dependency definitions
├── manage.py                  # Django CLI runner
├── DESIGN.md                  # Two-page architectural specification & ER diagram
├── DEMO_SCRIPT.md             # 8-minute video presentation script
└── README.md                  # Master documentation
```

---

## 6. Database Overview
The PostgreSQL database consists of 18 relational tables:
- **Users & Auth**: `core_user`, `core_auditlog`
- **Master Data**: `master_data_unitofmeasure`, `master_data_productcategory`, `master_data_product`, `master_data_customer`, `master_data_supplier`, `master_data_pricelist`
- **Inventory**: `inventory_inventoryitem`, `inventory_stockledger`, `inventory_purchase`, `inventory_purchaseitem`
- **Production**: `production_billofmaterials`, `production_bomcomponent`, `production_productionrun`, `production_productionconsumption`
- **Sales & Billing**: `sales_salesorder`, `sales_salesorderitem`, `sales_invoice`, `sales_invoiceitem`, `sales_dispatch`, `sales_dispatchitem`, `sales_payment`, `sales_paymentallocation`, `sales_creditnote`

---

## 7. Features Implemented

### Sales & Distribution
- Mobile-first order booking interface for field salesmen.
- Automatic price determination with support for custom customer price books.
- Real-time subtotal, GST estimate, and order total calculation.
- Admin order verification, inline item editing, approval, and rejection workflows.
- Sequential GST invoice numbering by financial year (e.g. `INV-2627-0001`).
- Accurate tax classification:
  - Intra-state (Tamil Nadu to Tamil Nadu): CGST 2.5% + SGST 2.5%.
  - Inter-state (Tamil Nadu to Karnataka): IGST 5.0%.
- PDF Tax Invoice generation using ReportLab compliant with GST Rule 46.
- Lawful invoice cancellation via formal `CreditNote` workflow (original invoice retained intact).
- Dispatch control checking actual finished-goods stock and blocking overselling.
- Customer payment recording with multi-invoice allocation and real-time outstanding tracking.

### BOM & Manufacturing Execution
- Reusable, versioned Bill of Materials (BOM) with batch multiplier support.
- Real-time stock consumption deduction for raw materials and packaging.
- Separation of good pouches used vs damaged pouches recorded as scrap.
- Packaging capacity reconciliation: flags capacity warnings when outer cartons cannot hold actual output.
- Consumption variance calculation against standard recipe.
- Yield variance calculation against expected batch output.
- Automatic alert banners when variances breach the configurable tolerance (default 3%).
- Unit manufacturing absorption costing: direct materials + labour + overhead = cost per good packet.

### Perpetual Inventory & Cost Accounting
- Centralized unit conversion service preventing incompatible unit mixing.
- Weighted-Average Costing (WAC) recalculated atomically upon every purchase receipt.
- Atomic stock movements via `StockLedger` with balance before and balance after traceability.
- Prevention of negative inventory balances via database row locks (`select_for_update`).
- Live stock summary separating Raw Materials, Packaging, and Finished Goods.

### Audit & Reporting
- Executive Owner Dashboard with live KPI counters and interactive Chart.js analytics.
- Statutory GSTR-1 outward taxable supplies summary (B2B, B2C, HSN table).
- Statutory GSTR-3B Section 3.1 outward tax summary.
- Customer receivables aging report broken into 0–30, 31–60, 61–90, and >90 day brackets.
- One-click exports of all reports to CSV, Excel (`.xlsx`), and PDF.
- Immutable system audit trail logging user, entity, action, previous value, new value, and reason.

---

## 8. Role Descriptions & Access Control

| Role | Permitted Operations | Restricted Operations |
|---|---|---|
| **Salesman** | Mobile order entry, assigned customer view, order status, personal order history | Cannot access factory admin, production, or audit reports |
| **Factory Admin** | Review/edit incoming orders, approve/reject orders, generate GST invoices, record dispatch, record customer payments, manage master data | Cannot tamper with closed audit ledger entries |
| **Production Supervisor**| View raw material & packaging stock, record inward purchases, execute production runs, record consumption & output, view variance alerts | Cannot modify sales orders, invoices, or financial ledgers |
| **Accountant / Auditor** | Read-only access to all reports, sales register, GSTR-1, GSTR-3B, production costing, stock ledger, export to CSV/Excel/PDF | Strict read-only mode; cannot alter or delete transactions |
| **Factory Owner** | Executive dashboard, real-time KPI metrics, sales vs cost analytics, inventory valuation, receivables summary, all audit logs | Executive overview of all factory performance |

---

## 9. Feature Status Matrix

### Must-Have Features (Completed: 100%)
- [x] Multi-role authentication & backend permission decorators
- [x] Master data CRUD (Products, Customers, Suppliers, Units)
- [x] Reusable BOM with versioning
- [x] Weighted-Average Costing (WAC) on purchase receipts
- [x] Production run execution with actual consumption recording
- [x] Planned vs actual material variance calculation & alerts
- [x] Expected vs actual yield variance calculation & alerts
- [x] Packaging damage and capacity warning reconciliation
- [x] Salesman mobile order entry
- [x] Admin order review & inline item modification
- [x] GST Tax Invoicing (CGST+SGST vs IGST)
- [x] Controlled dispatch with shortage detection & prevention of negative stock
- [x] Customer payment receipt & outstanding balance tracking
- [x] PDF Tax Invoice download via ReportLab
- [x] Perpetual Stock Movement Ledger
- [x] Statutory reports: Sales Register, GSTR-1 Summary, GSTR-3B Summary, Production Costing, Receivables Aging
- [x] Multi-format exports: CSV, Excel, PDF

### Should-Have Features (Completed: 100%)
- [x] Interactive Chart.js analytics on Owner Dashboard
- [x] One-click demo credential switcher on login page
- [x] Automated unit conversion calculator tool in UI
- [x] Credit Note cancellation workflow retaining original invoices
- [x] Comprehensive automated test suite validating items A through S

### Stretch Goals (Status)
- [x] Centralized unit conversion service for cartons to packets
- [x] Multi-format report export suite (CSV + Excel + PDF)
- [ ] Offline PWA service-worker order capture (stretch goal omitted to prioritize core reliability)

---

## 10. Local Setup Instructions (Without Docker)

### Prerequisites
- Python 3.11 or higher installed on your system.
- PostgreSQL 14+ installed and running locally on port 5432.

### Step 1: Clone or Navigate to Project Directory
```powershell
cd "C:\Users\user\Documents\Order-to-Audit System"
```

### Step 2: Configure Environment Variables
Verify `.env` in the project root:
```ini
SECRET_KEY=django-insecure-order-to-audit-nit-trichy-challenge-super-secret-key-2026
DEBUG=True
ALLOWED_HOSTS=*
DB_ENGINE=django.db.backends.postgresql
DB_NAME=ordertoaudit
DB_USER=postgres
DB_PASSWORD=1234
DB_HOST=localhost
DB_PORT=5432
FACTORY_STATE=Tamil Nadu
FACTORY_GSTIN=33AAAAA0000A1Z5
FACTORY_NAME=Sri Krishna Food Products
FACTORY_ADDRESS=Plot 12, SIDCO Industrial Estate, Thuvakudi, Trichy - 620015, Tamil Nadu
```

### Step 3: Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Apply Database Migrations
```powershell
python manage.py migrate
```

### Step 5: Seed Master Data & Run Benchmark Scenario
```powershell
# 1. Seed initial demo users, master product, customers, opening stock, and BOM:
python manage.py seed_benchmark

# 2. Execute and verify the complete 9-step benchmark scenario end-to-end:
python manage.py run_benchmark_scenario --reset
```

### Step 6: Start the Development Server
```powershell
python manage.py runserver 8000
```
Open your browser and navigate to: `http://localhost:8000/`

---

## 11. Demo Login Credentials

The login page at `http://localhost:8000/login/` features **one-click demo login buttons** for evaluator convenience. All demo accounts use the standard password: `pass1234`

| Username | Role | Purpose / Views |
|---|---|---|
| `salesman_a` | Salesman | Mobile order booking, assigned customers (Retailer A - Tamil Nadu) |
| `salesman_b` | Salesman | Mobile order booking, assigned customers (Distributor B - Karnataka) |
| `factory_admin` | Factory Admin | Order approvals, GST invoicing, dispatch, payments, master data |
| `production_sup`| Production Supervisor| Inward purchase receipts, BOM recipes, production runs, variance review |
| `auditor` | Accountant / Auditor | Read-only access to all registers, GSTR-1, GSTR-3B, costing, aging, exports |
| `owner` | Factory Owner | Executive dashboard, live KPI cards, sales vs cost analytics |

---

## 12. Benchmark Verification Results

The application demonstrates and validates all 9 benchmark steps with 100% mathematical precision:

| Step | Operation | System Execution & Output | Benchmark Requirement | Status |
|---|---|---|---|---|
| **Step 1** | Purchase 60 kg flour @ ₹45/kg | Flour stock: 100 + 60 = 160 kg. WAC = (100×42 + 60×45)/160 = ₹43.1250/kg | 160 kg @ ₹43.1250/kg | **PASS** |
| **Step 2** | Murukku 200g Production Run | Issued: Flour 40 kg, Oil 10.5 L, Spice 1.2 kg. Actual good output: 188 pkts. Pouches damaged: 6. Cartons: 9 | 188 good pkts, 6 damaged, 9 cartons | **PASS** |
| **Step 3** | Closing Inventory Balances | Flour: 120 kg, Oil: 19.5 L, Spice: 3.8 kg, Pouches: 306 pcs, Cartons: 21 pcs, FG: 238 pkts | Exact match across all balances | **PASS** |
| **Step 3b**| Production Variances | Yield: -6.00% (Flagged). Oil: +5.00% (Flagged). Packaging Warning: 9 cartons hold 180 pkts (< 188) | Flagged > 3% tolerance + capacity warning | **PASS** |
| **Step 4** | Salesman A Order (Retailer A) | Order SO-BENCH-001 submitted for 150 pkts @ ₹50 | Subtotal ₹7,500, Tax ₹375 | **PASS** |
| **Step 5** | Admin Approval & Invoicing | Invoice INV-2627-0001: Taxable ₹7,500, CGST ₹187.50, SGST ₹187.50, Total ₹7,875 | Intra-state CGST + SGST = ₹7,875 | **PASS** |
| **Step 5b**| Order Dispatch | Dispatched 150 pkts. Finished Goods stock: 238 - 150 = 88 packets | Closing FG = 88 packets | **PASS** |
| **Step 6** | Distributor B Shortage Check | Order for 120 pkts. Stock: 88 pkts. Shortage: 32 pkts. Dispatch blocked to prevent negative inventory | Invalid dispatch prevented & shortage flagged | **PASS** |
| **Step 7** | Customer Payment Receipt | Received ₹4,000 from Retailer A. Outstanding due: ₹7,875 - ₹4,000 = ₹3,875 | Outstanding = ₹3,875 | **PASS** |
| **Step 8** | Production Costing | Materials: ₹4,055 + Labour: ₹1,200 + Overhead: ₹600 = ₹5,855. Cost/Pkt: ₹5,855 / 188 = ₹31.14 | Total ₹5,855; Cost/Pkt ₹31.14 | **PASS** |
| **Step 9** | Monthly Reports Validation | Sales Register, GSTR-1, GSTR-3B, Costing, Receivables Ageing generated from stored transactions | Fully reconciled & exportable | **PASS** |

---

## 13. Automated Test Execution & Results

Run the automated test suite using Django's test framework:
```powershell
python manage.py test
```

### Actual Test Suite Execution Output
```
Creating test database for alias 'default'...
........
----------------------------------------------------------------------
Ran 8 tests in 70.904s

OK
Destroying test database for alias 'default'...
Found 8 test(s).
System check identified no issues (0 silenced).
```

### Verified Test Cases Breakdown
- `test_a_weighted_average_flour_valuation`: Validates purchase calculation and WAC adjustment to ₹43.1250/kg.
- `test_b_through_j_production_and_variances`: Validates exact closing stocks (120 kg flour, 19.5 L oil, 3.8 kg spice, 306 pouches, 21 cartons, 238 FG), yield variance (-6%), oil variance (+5%), and costing (₹5,855 total, ₹31.14/pkt).
- `test_k_gst_invoicing_and_dispatch`: Validates sequential invoicing, CGST/SGST tax math, dispatch stock reduction to 88 packets, and partial payment reconciliation.
- `test_m_distributor_b_shortage_validation`: Asserts that an invalid dispatch for 120 packets against 88 available raises a `ValidationError` and preserves stock balance.
- `test_o_role_permissions`: Validates that salesmen are blocked (HTTP 403) from administrative audit trail endpoints.
- `test_p_credit_note_workflow`: Validates lawful invoice cancellation via credit note.
- `test_q_stock_ledger_reconciliation`: Validates that ledger `balance_before` and `balance_after` match current stock.
- `test_r_duplicate_dispatch_prevention`: Asserts that an already-dispatched order cannot be dispatched again.

---

## 14. Stock Valuation & Costing Methodology
1. **Weighted Average Costing (WAC)**:
   Whenever an inward purchase receipt is posted, the new unit cost is computed as:
   $$\text{WAC} = \frac{\text{Current Stock Value} + \text{Purchase Amount}}{\text{Current Stock Quantity} + \text{Purchase Quantity}}$$
2. **Absorption Costing for Production**:
   Direct materials are issued at their current WAC. Direct manufacturing labour and utility overheads (power/gas) are absorbed into the batch. The unit cost per good packet is determined by dividing total batch manufacturing cost by actual good output packets. Damaged pouches and unboxed overflows are recognized as direct manufacturing scrap.

---

## 15. Key Engineering Assumptions & Notes
1. **Packaging Capacity Inconsistency**:
   Standard outer cartons hold 20 packets. 9 cartons can hold 180 packets, whereas actual good output is 188 packets. As instructed, 9 cartons are deducted from inventory (leaving 21 cartons), and the application displays an explicit packaging capacity warning explaining the 8-packet overflow.
2. **Place of Supply**:
   The factory is registered in Tamil Nadu (State Code 33). Supplies to customers in Tamil Nadu are treated as intra-state (CGST 2.5% + SGST 2.5%). Supplies to customers in other states (e.g. Karnataka) are treated as inter-state (IGST 5.0%).
3. **No Silent Deletions**:
   Posted invoices are never deleted. Cancellation is handled lawfully via a formal credit note workflow.

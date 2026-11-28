# Sri Krishna Food Products – Order-to-Audit ERP

### Integrated ERP System for Packaged Food Manufacturing

**Internship Project – Centre for Digital Infrastructure, National Institute of Technology Tiruchirappalli (NIT Trichy)**

---

## 1. Project Overview

Sri Krishna Food Products – Order-to-Audit ERP is a web-based Enterprise Resource Planning system designed for a small-scale packaged food manufacturing business producing traditional South Indian snacks.

The system integrates major business operations, including sales, inventory, purchasing, manufacturing, GST invoicing, customer payments, production costing and audit reporting into a centralized application.

The primary objective is to reduce manual record-keeping, improve coordination between departments, monitor raw-material consumption, track production performance and provide better visibility into business operations.

The application connects two major workflows:

**Sales Workflow:**

Salesman Order → Admin Verification → Order Approval → GST Invoice → Dispatch → Customer Payment → Receivables Reporting

**Production Workflow:**

Raw Material Inventory → Bill of Materials (BOM) → Production Execution → Material Consumption → Finished Goods → Costing and Yield Variance

Both workflows contribute to inventory records and business reports.

---

## 2. Problem Being Solved

Small food manufacturing businesses often manage sales, inventory, production and accounting-related activities separately.

Common challenges include:

- Sales orders being communicated through phone calls or messaging applications.
- Manual entry of customer orders and invoices.
- Difficulty tracking raw-material consumption during manufacturing.
- Lack of visibility into production wastage and yield differences.
- Difficulty calculating manufacturing cost per packet.
- Manual preparation of sales, GST, inventory and payment reports.

This ERP system aims to address these challenges by connecting business operations through a centralized database and providing role-based access to different departments.

---

## 3. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming language |
| Django 5.2 | Web application framework |
| Django REST Framework | REST API development |
| PostgreSQL | Relational database |
| HTML5 | Frontend page structure |
| CSS3 | User interface styling |
| Bootstrap | Responsive frontend design |
| JavaScript | Frontend interactions |
| ReportLab | PDF document generation |
| OpenPyXL | Excel workbook handling |

### Why This Technology Stack?

**Python and Django:** Django provides a structured framework for developing database-driven web applications with authentication, ORM support and security features.

**PostgreSQL:** PostgreSQL provides relational data storage and transaction management for business records.

**Bootstrap:** Bootstrap supports responsive user interfaces for desktop and mobile devices.

**ReportLab and OpenPyXL:** These libraries support PDF document generation and Excel reporting.

This technology combination provides a practical foundation for developing an integrated ERP application.

---

## 4. System Architecture

The project follows a modular Django application structure. Each application handles a specific business area.

### Django Applications

| Application | Responsibility |
|---|---|
| `apps.core` | User authentication, role management and dashboard functionality |
| `apps.master_data` | Products, customers, suppliers and units of measurement |
| `apps.inventory` | Inventory items, stock balances, purchases and stock movements |
| `apps.production` | Bill of Materials, production runs and manufacturing costing |
| `apps.sales` | Sales orders, invoices, dispatches and customer payments |
| `apps.reports` | Audit reports, GST summaries, costing and receivables reporting |

### Project Directory Structure

```text
Order-to-Audit-System/
│
├── apps/
│   ├── core/
│   ├── inventory/
│   ├── master_data/
│   ├── production/
│   ├── reports/
│   └── sales/
│
├── templates/
├── static/
├── manage.py
├── requirements.txt
├── .env
└── README.md
```

The `.env` file contains environment-specific settings and must not be committed to the public repository.

---

## 5. Features Implemented

### 5.1 Sales Management

- Salesman login and customer order booking.
- Customer and product selection.
- Sales order creation and tracking.
- Factory Admin order verification.
- Order approval and processing.
- GST invoice generation.
- Order dispatch management.
- Customer payment recording.

### 5.2 Master Data Management

- Product management.
- Product category management.
- Unit of Measurement (UOM) management.
- Customer management.
- Supplier management.
- Raw-material and packaging-item management.

### 5.3 Inventory Management

- Opening stock management.
- Raw-material inventory tracking.
- Packaging-material inventory tracking.
- Finished-goods inventory tracking.
- Weighted Average Cost (WAC) valuation.
- Stock balances and valuation.
- Stock movement ledger.
- Purchase and goods receipt records.
- Inventory movement tracking for production and dispatch.

### 5.4 Production Management

- Bill of Materials (BOM) creation.
- Recipe-based production planning.
- Production batch execution.
- Actual material consumption recording.
- Finished-product output recording.
- Damaged packaging and wastage recording.
- Labour and manufacturing overhead recording.
- Production run history.
- Planned versus actual production comparison.
- Yield variance monitoring.
- Configurable production variance tolerance.

### 5.5 GST Invoicing and Payments

- GST invoice generation.
- Taxable value calculation.
- GST calculation.
- CGST and SGST for applicable intra-state transactions.
- Customer payment recording.
- Outstanding payment tracking.
- Invoice and payment reference management.

### 5.6 Audit and Compliance Reports

The Accountant / Auditor role provides access to the following modules:

**Inventory & Stock**
- Stock Balances (WAC)
- Stock Movement Ledger
- Purchases & Receipts

**Audit & Compliance**
- Audit Command Center
- Sales Register
- GSTR-1 Outward Supplies
- Costing & Yield Variance
- Receivables Ageing

These reports support inventory review, sales verification, GST reporting, production cost analysis and customer outstanding monitoring.

### 5.7 Owner Dashboard

- Executive business overview.
- Sales information.
- Inventory information.
- Production performance.
- Outstanding receivables.
- Operational monitoring.

---

## 6. User Roles and Access Control

The application implements role-based access control to provide different functionalities according to user responsibilities.

| Role | Username | Main Responsibilities |
|---|---|---|
| Factory Admin | `factory_admin` | Master data, inventory, order approval, invoicing, dispatch and payments |
| Salesman | `salesman_a` | Customer order booking and order tracking |
| Production Supervisor | `production_sup` | BOM management and production execution |
| Accountant / Auditor | `auditor` | Inventory review, costing and audit reports |
| Owner | `owner` | Executive dashboard and business monitoring |

Each role has access to its relevant application modules and operations.

---

## 7. Demonstration Scenario

The project uses a South Indian snack manufacturing scenario based on Murukku 200 g.

### Product Information

| Field | Value |
|---|---|
| Product Name | Murukku 200 g |
| SKU | MUR-200 |
| Category | Traditional Savouries |
| Selling Price | ₹50 per packet |
| GST Rate | 5% |
| HSN Code | 19059040 |

### Production Scenario

The demonstration includes two production runs.

| Production Run | Good Output | Production Cost | Cost per Packet |
|---|---:|---:|---:|
| PR-2627-0001 | 186 packets | ₹5,735 | ₹30.83 |
| PR-2627-0002 | 200 packets | ₹5,620 | ₹28.10 |
| **Total** | **386 packets** | **₹11,355** | **Approximately ₹29.42 weighted average** |

The first production run recorded a yield variance of -7%, exceeding the configured 3% tolerance.

The second production run recorded 0% yield variance.

### Sales Scenario

A sales order is created for Retailer A for 150 packets of Murukku.

| Particular | Amount |
|---|---:|
| Quantity | 150 packets |
| Taxable Value | ₹7,500 |
| CGST | ₹187.50 |
| SGST | ₹187.50 |
| Invoice Total | ₹7,875 |
| Payment Received | ₹4,000 |
| Outstanding Amount | ₹3,875 |

The sales workflow demonstrates order booking, approval, GST invoicing, dispatch and payment recording.

---

## 8. Benchmark Differences and Assumptions

The internship problem statement specifies a benchmark scenario with one production run, an opening finished-goods balance of 50 packets, 188 good packets produced and 10.5 litres of oil consumed.

The current demonstration dataset differs from that benchmark.

| Benchmark Requirement | Current Demonstration |
|---|---|
| Opening finished goods: 50 packets | Opening finished goods: 0 packets |
| One production run | Two production runs |
| First-run output: 188 packets | First-run output: 186 packets |
| Oil consumption: 10.5 litres | First-run consumption: 10 litres |
| Expected yield: 200 packets | Expected yield: 200 packets |
| Retailer A order: 150 packets | Retailer A order: 150 packets |

The recorded production runs generated 386 packets in total.

After dispatching 150 packets, the stock movement ledger indicates 236 packets remaining.

The weighted average production cost across the two recorded runs is approximately ₹29.42 per packet.

These figures represent the current demonstration dataset and are not an exact reproduction of every benchmark result.

### Known Inventory Valuation Limitation

During demonstration validation, a discrepancy was identified between the finished-goods stock movement ledger and the finished-goods valuation displayed in the stock summary and executive dashboard.

The ledger indicates 236 packets remaining after dispatch, while the stock summary and dashboard display finished-goods value as ₹0.

This requires further investigation and reconciliation before the finished-goods valuation can be treated as fully verified.

---

## 9. Stock Valuation and Production Costing

### Weighted Average Costing (WAC)

The system uses the Weighted Average Cost method for inventory valuation.

The calculation is:

**Weighted Average Cost = (Existing Stock Value + Purchase Value) / (Existing Stock Quantity + Purchased Quantity)**

This method calculates an average unit cost after stock receipts.

### Production Costing

Manufacturing cost includes:

- Direct raw-material cost.
- Packaging-material cost.
- Labour cost.
- Manufacturing overheads such as gas and electricity.

The cost per good packet is calculated as:

**Cost per Packet = Total Production Cost / Actual Good Output**

The production costing module helps compare manufacturing costs and identify production losses and yield differences.

---

## 10. Installation and Setup

### Prerequisites

- Python 3.11 or later.
- PostgreSQL database.
- Git.
- pip.

### Step 1: Clone the Repository

```bash
git clone https://github.com/supreeth-gunnala/Order-to-Audit-System.git
```

### Step 2: Navigate to the Project Directory

```bash
cd Order-to-Audit-System
```

### Step 3: Create a Virtual Environment

```bash
python -m venv venv
```

Activate the environment on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Configure Environment Variables

Create a `.env` file in the project root.

Configure the PostgreSQL connection using your own database details.

Example:

```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=your_database_host
DB_PORT=5432
```

Configure other required Django settings according to the project's settings module.

**Important:** Never publish database passwords, secret keys or private connection strings in GitHub.

### Step 6: Apply Database Migrations

```bash
python manage.py migrate
```

### Step 7: Create an Administrator Account

```bash
python manage.py createsuperuser
```

### Step 8: Run the Development Server

```bash
python manage.py runserver
```

Open the application in your browser:

```text
http://127.0.0.1:8000/
```

For a fresh database, configure the required user roles and master data before using the business workflows.

---

## 11. Demonstration Login Credentials

The prepared demonstration database contains the following accounts.

All five demonstration accounts use the same temporary demonstration password.

**Password:** `pass1234`

| Username | Role |
|---|---|
| `factory_admin` | Factory Admin |
| `salesman_a` | Salesman |
| `production_sup` | Production Supervisor |
| `auditor` | Accountant / Auditor |
| `owner` | Owner |

These credentials are intended only for the prepared demonstration environment. Change them before any public or production deployment.

A fresh database created using the installation instructions will require its own user and master-data setup.

---

## 12. Project Links

**GitHub Repository**

https://github.com/supreeth-gunnala/Order-to-Audit-System

**Live Application**

https://order-to-audit-system-tan.vercel.app

**Project Demonstration Video**

https://youtu.be/YoP74DsE0j8?si=cBbKkTnL5R7fQ3E3

---

## 13. Known Limitations and Future Enhancements

The following areas can be improved in future versions:

- Reconciliation of finished-goods valuation across inventory reports and the dashboard.
- Further validation of the complete internship benchmark scenario.
- Dedicated Profit and Loss reporting.
- Additional automated tests for stock calculations, GST and production costing.
- Improved offline order capture and synchronization.
- Batch number and expiry-date tracking.
- Low-stock alerts and reorder-level management.
- Production planning based on pending customer orders.
- Further improvements to accounting and audit exports.

---

## 14. Conclusion

Sri Krishna Food Products – Order-to-Audit ERP demonstrates how different operational activities of a small food manufacturing business can be integrated through a centralized web application.

By connecting sales, inventory, purchasing, production, GST invoicing, customer payments and audit reporting, the system aims to reduce manual work, improve operational visibility and support better business decisions.

The project provided practical experience in Python, Django, PostgreSQL, database management, role-based access control, business workflow design and ERP application development.

---

**Project Type:** Individual Internship Project

**Institution:** National Institute of Technology Tiruchirappalli (NIT Trichy)

**Centre:** Centre for Digital Infrastructure

**Project:** Sri Krishna Food Products – Order-to-Audit ERP

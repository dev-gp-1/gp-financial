-- ═══════════════════════════════════════════════════════════════
-- GAA Financial Ledger — Multi-Tenant Schema
-- Supports: AR, AP, Invoicing, Receipts, Transactions, Line Items
-- Dataset: gaa_financial | Project: tron-cloud
-- ═══════════════════════════════════════════════════════════════

-- 1. TENANTS — Multi-tenant isolation
CREATE TABLE IF NOT EXISTS gaa_financial.tenants (
  tenant_id STRING NOT NULL,
  name STRING NOT NULL,
  dba_name STRING,
  entity_type STRING,
  industry STRING,
  tax_id STRING,
  primary_contact_email STRING,
  billing_address STRING,
  status STRING DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 2. ENTITIES — Vendors, Customers, Subcontractors
CREATE TABLE IF NOT EXISTS gaa_financial.entities (
  entity_id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  name STRING NOT NULL,
  entity_role STRING NOT NULL,
  email STRING,
  phone STRING,
  address STRING,
  tax_id STRING,
  payment_terms STRING,
  default_gl_code STRING,
  qbo_id STRING,
  r365_id STRING,
  mercury_recipient_id STRING,
  stripe_customer_id STRING,
  status STRING DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 3. CHART OF ACCOUNTS
CREATE TABLE IF NOT EXISTS gaa_financial.chart_of_accounts (
  account_id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  account_code STRING NOT NULL,
  account_name STRING NOT NULL,
  account_type STRING NOT NULL,
  account_subtype STRING,
  parent_account_id STRING,
  tax_code STRING,
  is_active BOOL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 4. INVOICES — Unified AR/AP
CREATE TABLE IF NOT EXISTS gaa_financial.invoices (
  invoice_id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  invoice_number STRING NOT NULL,
  direction STRING NOT NULL,
  entity_id STRING NOT NULL,
  status STRING DEFAULT 'draft',
  issue_date DATE NOT NULL,
  due_date DATE NOT NULL,
  currency STRING DEFAULT 'USD',
  subtotal NUMERIC,
  tax_amount NUMERIC DEFAULT 0,
  discount_amount NUMERIC DEFAULT 0,
  total_amount NUMERIC NOT NULL,
  amount_paid NUMERIC DEFAULT 0,
  balance_due NUMERIC,
  payment_terms STRING,
  notes STRING,
  internal_memo STRING,
  pdf_url STRING,
  stripe_payment_link STRING,
  paypal_invoice_id STRING,
  qbo_invoice_id STRING,
  r365_invoice_id STRING,
  service_period_start DATE,
  service_period_end DATE,
  approved_by STRING,
  approved_at TIMESTAMP,
  sent_at TIMESTAMP,
  paid_at TIMESTAMP,
  voided_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 5. INVOICE LINE ITEMS
CREATE TABLE IF NOT EXISTS gaa_financial.invoice_lines (
  line_id STRING NOT NULL,
  invoice_id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  line_number INT64,
  description STRING NOT NULL,
  gl_account_id STRING,
  quantity NUMERIC DEFAULT 1,
  unit_price NUMERIC NOT NULL,
  amount NUMERIC NOT NULL,
  tax_rate NUMERIC DEFAULT 0,
  tax_amount NUMERIC DEFAULT 0,
  discount_percent NUMERIC DEFAULT 0,
  service_date DATE,
  project_code STRING,
  department STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 6. TRANSACTIONS
CREATE TABLE IF NOT EXISTS gaa_financial.transactions (
  transaction_id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  source STRING NOT NULL,
  source_transaction_id STRING,
  transaction_type STRING,
  raw_description STRING,
  enriched_description STRING,
  enriched_category STRING,
  vendor_name STRING,
  entity_id STRING,
  amount NUMERIC NOT NULL,
  currency STRING DEFAULT 'USD',
  transaction_date DATE NOT NULL,
  posted_date DATE,
  gl_account_id STRING,
  tax_code STRING,
  tax_deductible BOOL,
  invoice_id STRING,
  reconciliation_status STRING DEFAULT 'unmatched',
  reconciliation_method STRING,
  reconciled_at TIMESTAMP,
  confidence_score FLOAT64,
  anomaly_flag BOOL DEFAULT FALSE,
  anomaly_reason STRING,
  bank_account_id STRING,
  check_number STRING,
  memo STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  enriched_at TIMESTAMP
);

-- 7. PAYMENTS
CREATE TABLE IF NOT EXISTS gaa_financial.payments (
  payment_id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  invoice_id STRING,
  transaction_id STRING,
  entity_id STRING NOT NULL,
  payment_type STRING NOT NULL,
  payment_method STRING,
  amount NUMERIC NOT NULL,
  currency STRING DEFAULT 'USD',
  payment_date DATE NOT NULL,
  reference_number STRING,
  direction STRING NOT NULL,
  status STRING DEFAULT 'pending',
  approved_by STRING,
  approved_at TIMESTAMP,
  notes STRING,
  mercury_payment_id STRING,
  stripe_payment_intent_id STRING,
  paypal_capture_id STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  completed_at TIMESTAMP
);

-- 8. RECEIPTS
CREATE TABLE IF NOT EXISTS gaa_financial.receipts (
  receipt_id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  transaction_id STRING,
  invoice_id STRING,
  entity_id STRING,
  receipt_date DATE,
  amount NUMERIC,
  currency STRING DEFAULT 'USD',
  description STRING,
  category STRING,
  file_url STRING,
  file_type STRING,
  ocr_text STRING,
  ocr_confidence FLOAT64,
  tax_deductible BOOL,
  gl_account_id STRING,
  status STRING DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  processed_at TIMESTAMP
);

-- 9. JOURNAL ENTRIES — Double-entry accounting
CREATE TABLE IF NOT EXISTS gaa_financial.journal_entries (
  entry_id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  entry_date DATE NOT NULL,
  reference STRING,
  description STRING,
  source STRING,
  source_id STRING,
  status STRING DEFAULT 'posted',
  created_by STRING,
  approved_by STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 10. JOURNAL LINES — Debit/Credit entries
CREATE TABLE IF NOT EXISTS gaa_financial.journal_lines (
  line_id STRING NOT NULL,
  entry_id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  gl_account_id STRING NOT NULL,
  debit_amount NUMERIC DEFAULT 0,
  credit_amount NUMERIC DEFAULT 0,
  entity_id STRING,
  department STRING,
  project_code STRING,
  memo STRING
);

-- 11. ENRICHMENT LOG — AI audit trail
CREATE TABLE IF NOT EXISTS gaa_financial.enrichment_log (
  log_id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  source_type STRING NOT NULL,
  source_id STRING NOT NULL,
  model_used STRING,
  prompt_tokens INT64,
  completion_tokens INT64,
  enrichment_type STRING,
  input_text STRING,
  output_json STRING,
  confidence FLOAT64,
  processing_ms INT64,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

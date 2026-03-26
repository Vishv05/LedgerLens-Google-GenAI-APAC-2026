-- SmartSpend sample table and seed data
CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    amount INTEGER NOT NULL,
    date DATE NOT NULL,
    payment_mode TEXT NOT NULL
);

INSERT INTO expenses (category, amount, date, payment_mode) VALUES
('Food', 450, '2026-03-01', 'UPI'),
('Transport', 250, '2026-03-02', 'Cash'),
('Shopping', 1200, '2026-03-03', 'Credit Card'),
('Food', 320, '2026-03-04', 'Debit Card'),
('Utilities', 900, '2026-03-05', 'UPI'),
('Health', 700, '2026-03-06', 'Credit Card'),
('Entertainment', 650, '2026-03-07', 'UPI');

# SQL vs pandas validation

Database: `sqlite` · queries: `analysis/sql/analysis_queries.sql` · pandas: `foodspend_core` on `data/processed/*.csv`

| Check | SQL | pandas | Result |
|---|---:|---:|---|
| total spending (INR) | 148988.1 | 148988.1 | PASS |
| transactions | 648 | 648 | PASS |
| component: items_subtotal | 131221.0 | 131221.0 | PASS |
| component: discounts | 3223.0 | 3223.0 | PASS |
| component: tax | 4755.1 | 4755.1 | PASS |
| component: delivery_fees | 13165.0 | 13165.0 | PASS |
| component: other_charges | 3070.0 | 3070.0 | PASS |
| monthly spending: months | 13 | 13 | PASS |
| monthly spending: max abs diff | 0.0 | 0 | PASS |
| category: Beverages | 4755.0 | 4755.0 | PASS |
| category: Biryani | 18525.0 | 18525.0 | PASS |
| category: Bowls & Salads | 11980.0 | 11980.0 | PASS |
| category: Dairy | 4344.99 | 4344.99 | PASS |
| category: Desserts | 1095.0 | 1095.0 | PASS |
| category: Eggs | 6090.88 | 6090.88 | PASS |
| category: Fast Food | 7425.0 | 7425.0 | PASS |
| category: Fruit | 8475.45 | 8475.45 | PASS |
| category: Indo-Chinese | 15420.0 | 15420.0 | PASS |
| category: North Indian | 22190.0 | 22190.0 | PASS |
| category: Sides | 2290.0 | 2290.0 | PASS |
| category: Snacks | 17484.68 | 17484.68 | PASS |
| category: South Indian | 11145.0 | 11145.0 | PASS |
| category: Order-level charges (tax + fees - discounts) | 17767.1 | 17767.1 | PASS |
| naive join overstates spending (expected) | 289342.67 | 148988.1 | PASS |
| top food events: Masala Chai | 110 | 110 | PASS |
| top food events: Boiled Eggs | 71 | 71 | PASS |
| top food events: Curd (Dahi) | 71 | 71 | PASS |
| top food events: Banana | 71 | 71 | PASS |
| top food events: Samosa (2 pcs) | 45 | 45 | PASS |
| top food events: Masala Dosa | 44 | 44 | PASS |
| top food events: Chicken Biryani | 43 | 43 | PASS |
| top food events: Paneer Butter Masala with 2 Roti | 42 | 42 | PASS |
| top food events: Veg Hakka Noodles | 40 | 40 | PASS |
| top food events: Mixed Nuts | 36 | 36 | PASS |
| avg daily logged kcal | 1434.1 | 1434.1 | PASS |
| avg daily logged protein | 50.9 | 50.9 | PASS |
| days logged | 346 | 346 | PASS |
| meal items with unknown fibre | 57 | 57 | PASS |
| mean rating: Masala Dosa | 4.31 | 4.31 | PASS |
| mean rating: Dal Tadka with Jeera Rice | 4.0 | 4.0 | PASS |
| mean rating: Chicken Biryani | 4.62 | 4.62 | PASS |
| mean rating: Masala Chai | 4.15 | 4.15 | PASS |
| mean rating: Home Dal, Rice and Sabzi Thali | 3.82 | 3.82 | PASS |
| mean rating: Egg Curry with 2 Roti | 3.64 | 3.64 | PASS |
| mean rating: Chicken Fried Rice | 3.7 | 3.7 | PASS |
| mean rating: Poha | 4.22 | 4.22 | PASS |
| mean rating: Idli Sambar (3 idli) | 4.0 | 4.0 | PASS |
| mean rating: Paneer Butter Masala with 2 Roti | 4.38 | 4.38 | PASS |

**48 / 48 checks passed.**

// Product catalog for the Coffee House demo shop.
// item_id values must stay identical everywhere (dataLayer, Meta content_ids, backend) – see tracking plan.
const PRODUCTS = [
  { item_id: 'SKU-101', item_name: 'Espresso Beans 1kg', item_category: 'Beans', price: 24.90,
    description: 'Dark roast, chocolate and hazelnut notes. Made for espresso machines.' },
  { item_id: 'SKU-102', item_name: 'Filter Beans 500g', item_category: 'Beans', price: 12.90,
    description: 'Light roast with fruity acidity. Ideal for pour-over and French press.' },
  { item_id: 'SKU-201', item_name: 'Hand Grinder', item_category: 'Grinders', price: 49.00,
    description: 'Steel burr hand grinder with 30 grind settings.' },
  { item_id: 'SKU-202', item_name: 'Electric Burr Grinder', item_category: 'Grinders', price: 129.00,
    description: 'Consistent grind from espresso to cold brew at the push of a button.' },
  { item_id: 'SKU-301', item_name: 'Ceramic Mug', item_category: 'Mugs', price: 9.90,
    description: 'Handmade 300 ml ceramic mug.' },
  { item_id: 'SKU-302', item_name: 'Travel Mug', item_category: 'Mugs', price: 19.90,
    description: 'Insulated 400 ml travel mug, keeps coffee hot for 4 hours.' }
];

// "Customers also bought" recommendations, shown only in A/B variant B (BQ4).
const ALSO_BOUGHT = {
  'SKU-101': ['SKU-202', 'SKU-301'],
  'SKU-102': ['SKU-201', 'SKU-302'],
  'SKU-201': ['SKU-102', 'SKU-301'],
  'SKU-202': ['SKU-101', 'SKU-302'],
  'SKU-301': ['SKU-101', 'SKU-102'],
  'SKU-302': ['SKU-102', 'SKU-201']
};

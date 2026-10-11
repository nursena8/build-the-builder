// Test customers. Replace with the final case's test customers (convert the delivered table to this shape).
// identity values are what the customer knows; products come back from get_account. faults: [{tool, fail_first_n}] make a tool answer 500 first.
export const CUSTOMERS = [
  { customer_id: "c_demo_1", first_name: "Daniel", last_name: "Reyes", title: "Mr",
    identity: { date_of_birth: "1988-03-14", phone_last4: "2219" },
    products: [{ product_id: "p1", type: "credit_card", card_last4: "7740", past_due: 365, days_late: 8, minimum_payment: 109.5 }], faults: [] },
  { customer_id: "c_demo_2", first_name: "Grace", last_name: "Lin", title: "Ms",
    identity: { date_of_birth: "1989-02-23", phone_last4: "9904" },
    products: [{ product_id: "p1", type: "credit_card", card_last4: "7740", past_due: 365, days_late: 8, minimum_payment: 109.5 }],
    faults: [{ tool: "create_promise", fail_first_n: 1 }] },
];

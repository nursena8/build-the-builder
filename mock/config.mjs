// Rules of the bank's services. Adapt from the final case's service contract; nothing here is read from the case automatically.
export const CONFIG = {
  // identity: the fields a customer is asked, and how many wrong answers (in total) end the check
  identityFields: ["date_of_birth", "phone_last4"],
  maxWrong: 3,
  // close_call: outcome -> allowed reasons ([] = no reason allowed, null = any). Practice values; replace from the service contract.
  outcomeReasons: {
    promise: [], paid: [],
    transferred: ["restructuring", "human", "support"],
    no_promise: ["refused", "hardship", "dispute", "service_error"],
    not_verified: ["failed", "declined"],
    not_reached: ["wrong_number", "unclear", "callback", "no_callback", "deceased"],
  },
  noteReasons: ["refused", "hardship", "dispute", "paid", "service_error"],
  queues: ["restructuring", "general", "support"],
  adminKey: "change-me",   // for POST /v1/admin/reset
};

-- disable plutu payment provider
UPDATE payment_provider
   SET plutu_access_token = NULL,
       plutu_secret_key = NULL,
       plutu_api_key = NULL;

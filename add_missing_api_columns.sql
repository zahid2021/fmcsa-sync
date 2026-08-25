-- Add the 2 SODA API fields that had no DB columns.
-- Safe: does not delete/truncate existing data.

ALTER TABLE fmcsaaa.carrierinformation_csv
  ADD COLUMN BUSINESS_ORG_ID TEXT NULL AFTER ORG,
  ADD COLUMN MCS150_UPDATE_CODE_ID TEXT NULL AFTER MCS150MILEAGEYEAR;

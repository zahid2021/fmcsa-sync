-- Run once in MySQL Workbench (makes PHY_ST / DOT filters fast)
USE fmcsaaa;

-- Ignore error if index already exists
CREATE INDEX idx_phy_st ON carrierinformation_csv (PHY_ST);
CREATE INDEX idx_dot_number ON carrierinformation_csv (DOT_NUMBER);
CREATE INDEX idx_act_stat ON carrierinformation_csv (ACT_STAT);
CREATE INDEX idx_name ON carrierinformation_csv (NAME(50));

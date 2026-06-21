# language: en
# BDD Spec — Row Level Security (P4-B)

@rls
Feature: Row level security rules
  As an administrator
  I need to define row-level access policies on datasets

  Scenario: List RLS rules
    When the client calls "/api/v1/rowlevelsecurity/"
    Then the response contains the RLS rule list

  Scenario: Create an RLS rule
    Given a dataset and a role exist
    When the user creates a new RLS rule
    Then the rule appears in the list

  Scenario: Edit an RLS rule
    Given an RLS rule exists
    When the user modifies its clause
    Then the change is persisted

  Scenario: Delete an RLS rule
    Given an RLS rule exists
    When the user deletes that rule
    Then the rule is no longer in the list

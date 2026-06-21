# language: en
# BDD Spec — Saved Queries (P4-A)

@saved_query
Feature: Saved SQL Lab queries
  As a SQL Lab user
  I need to save, list, edit and delete SQL queries for reuse

  Scenario: List saved queries
    When the client calls "/api/v1/saved_query/"
    Then the response contains the saved query list

  Scenario: Create a saved query
    Given a database with a schema exists
    When the user creates a saved query
    Then the saved query appears in the list

  Scenario: Edit a saved query
    Given a saved query exists
    When the user modifies its description
    Then the change is persisted

  Scenario: Delete a saved query
    Given a saved query exists
    When the user deletes that saved query
    Then the saved query is no longer in the list

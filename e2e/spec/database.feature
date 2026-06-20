# language: en
# BDD Spec — Database CRUD (P0-A)

@database
Feature: Database management
  As an administrator
  I need to create, edit, delete and test database connections

  Scenario: List all databases
    When the client calls "/api/v1/database"
    Then the result contains at least one database
    And the result contains a database named "examples"

  Scenario: Get database details
    Given there is a database with id=1
    When the client calls "/api/v1/database/{id}"
    Then the response has the matching id
    And the response contains a "database_name" field

  Scenario: Create a new database connection
    When the user creates a new PostgreSQL database named "e2e_pg_xxx"
    Then the database appears in the list
    And the database is queryable

  Scenario: Edit a database connection
    Given there is an editable database
    When the user renames it and toggles "expose_in_sqllab"
    Then the new values are persisted

  Scenario: Delete a database connection
    Given a temporary database has been created
    When the user deletes that database
    Then it no longer appears in the list

  Scenario: Test the database connection
    Given there is a database
    When the user clicks "Test connection"
    Then the response is not a 5xx error

  Scenario: UI "new database" entry is available
    When the user opens the database list page
    Then a "+ DATABASE" button is visible

  Scenario: UI database list renders rows
    When the user opens the database list page
    Then at least one row is visible

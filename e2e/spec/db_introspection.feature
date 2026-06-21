# language: en
# BDD Spec — Database introspection (P4-E)

@db_meta
Feature: Database metadata queries
  As a data engineer
  I need to introspect schemas, tables and functions in a database

  Scenario: List database schemas
    Given a database exists
    When the user calls "/api/v1/database/1/schemas/"
    Then the response contains the schema list

  Scenario: Get table metadata
    Given a table "birth_names" exists in the examples database
    When the user calls "/api/v1/database/1/table_metadata/?name=birth_names"
    Then the response contains the column list

  Scenario: List database functions
    Given a database exists
    When the user calls "/api/v1/database/1/function_names/"
    Then the response contains the function list

# language: en
# BDD Spec — SQL Lab advanced (P1-B)

@sqllab
Feature: SQL Lab advanced operations
  As an analyst
  I need multi-tab editing, CTAS, saved queries, history and CSV export

  Scenario: Multiple query tabs
    Given SQL Lab is open
    When the user opens multiple query tabs
    Then each tab runs independently

  Scenario: LIMIT clause is honored
    When the user runs a query with "LIMIT 10"
    Then the result contains at most 10 rows

  Scenario: CTAS creates a table
    When the user runs "CREATE TABLE x AS SELECT ..."
    Then the new table exists in the database
    And the new table is queryable

  Scenario: Save a query
    When the user clicks "Save"
    Then the query is stored in the saved queries

  Scenario: Query history
    Given the user has run queries
    When the user opens the query history
    Then the previous queries are listed

  Scenario: Export results to CSV
    Given a query has produced results
    When the user clicks "Download CSV"
    Then a CSV file is downloaded

  Scenario: Jinja template parameter
    Given a template parameter "{{ ds }}" is configured
    When the user runs a templated query
    Then the template is replaced with the actual value

  @v6.0
  Scenario: Async query execution
    Given the Celery worker is enabled
    When the user runs a long-running query
    Then the status becomes "Pending" / "Running"
    And it eventually completes

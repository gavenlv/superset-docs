# language: en
# BDD Spec — Chart CRUD (P0-C)

@chart
Feature: Chart CRUD
  As an analyst
  I need to create, edit, query, export and import charts

  Scenario: List all charts
    When the client calls "/api/v1/chart"
    Then the result contains at least one chart

  Scenario: Get chart details
    Given there is a chart with id=N
    When the client calls "/api/v1/chart/{id}"
    Then the response contains "viz_type" and "datasource"

  Scenario: Create a big_number chart via API
    Given a dataset is available
    When the user creates a big_number chart via the API
    Then the chart appears in the list

  Scenario: Edit a chart name and description
    Given a chart has been created
    When the user modifies its name and description
    Then the changes are persisted

  Scenario: Query a chart's data
    Given a chart exists
    When the client calls "/api/v1/chart/{id}/data"
    Then the response contains the query result

  Scenario: Delete a chart
    Given a temporary chart has been created
    When the user deletes that chart
    Then the chart no longer appears in the list

  Scenario: Export a chart to JSON
    Given a chart exists
    When the user exports the chart
    Then a JSON file containing the chart configuration is downloaded

  Scenario: Import a chart from JSON
    Given a chart export file exists
    When the user uploads that file
    Then a new chart is created

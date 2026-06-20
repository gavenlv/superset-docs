# language: en
# BDD Spec — Import / Export (P2-A)

@import_export
Feature: Import and export
  As an operator
  I need to migrate dashboards, charts and database configs between instances

  Scenario: Export database to YAML
    Given a database exists
    When the user exports the database
    Then a YAML file is produced

  Scenario: Export chart to YAML
    Given a chart exists
    When the user exports the chart
    Then a YAML file is produced

  Scenario: Export dashboard to ZIP
    Given a dashboard with charts exists
    When the user exports the dashboard
    Then a ZIP file is produced

  Scenario: Import chart from YAML
    Given a chart YAML file exists
    When the user imports that file
    Then a new chart is created

  Scenario: Import dashboard from ZIP
    Given a dashboard ZIP file exists
    When the user imports that file
    Then a new dashboard is created

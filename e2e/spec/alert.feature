# language: en
# BDD Spec — Alerts and reports (P2-B)

@alert
Feature: Alerts
  As an operator
  I need to configure SQL alerts and threshold rules

  Scenario: List alerts
    When the client calls "/api/v1/alert"
    Then the response contains the alert list

  Scenario: Create a SQL alert
    Given a dataset is available
    When the user creates a SQL alert
    Then the alert appears in the list

  Scenario: Edit alert threshold
    Given an alert exists
    When the user modifies the threshold
    Then the new threshold is saved

  Scenario: Delete an alert
    Given an alert exists
    When the user deletes that alert
    Then the alert is removed from the list

@report
Feature: Reports
  As an operator
  I need to schedule email reports

  Scenario: Create a report schedule
    Given a dashboard exists
    When the user creates a daily report
    Then the report appears in the list

  Scenario: List reports
    When the client calls the report list endpoint
    Then the response contains the report list

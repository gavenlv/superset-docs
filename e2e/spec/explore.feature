# language: en
# BDD Spec — Explore editor (P1-C)

@chart @explore
Feature: Explore editor
  As an analyst
  I need to configure dataset, metrics, groupby, filters, time range, save and download

  Scenario: Switch dataset
    Given the Explore editor is open
    When the user changes the dataset
    Then the editor reloads the new dataset's columns

  Scenario: Add a metric
    Given the dataset has numeric columns
    When the user adds "SUM(num)" as a metric
    Then the chart aggregates by that metric

  Scenario: Add a groupby dimension
    Given the dataset has a dimension column
    When the user adds a groupby
    Then the chart groups by that dimension

  Scenario: Add an adhoc filter
    Given the dataset has filterable columns
    When the user adds filter "country = 'US'"
    Then the result contains only US rows

  Scenario: Time range configuration
    Given the dataset has a time column
    When the user sets the time range to "Last 7 days"
    Then the chart shows the last 7 days only

  Scenario: Save the chart
    Given a chart exists in Explore
    When the user clicks "Save"
    Then the chart is stored in the chart library

  Scenario: Download CSV from Explore
    Given Explore has produced a result
    When the user clicks "Download CSV"
    Then a result CSV is downloaded

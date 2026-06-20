# language: en
# BDD Spec — Dataset CRUD (P0-B)

@database @dataset
Feature: Dataset management
  As an analyst
  I need to build virtual datasets from physical tables and configure columns / metrics

  Scenario: List all datasets
    When the client calls "/api/v1/dataset"
    Then the result contains at least 10 example datasets

  Scenario: Get dataset details
    Given there is a dataset with id=N
    When the client calls "/api/v1/dataset/{id}"
    Then the response contains all the dataset's columns

  Scenario: Create a virtual dataset from a physical table
    Given the "examples" database is available
    When the user creates a virtual dataset from the physical table "birth_names"
    Then the new dataset appears in the list

  Scenario: Edit dataset columns and metrics
    Given a virtual dataset exists
    When the user adds a column, removes a column, and adds a metric
    Then the changes are persisted

  Scenario: Create a calculated metric
    Given the dataset has numeric columns
    When the user adds metric "sum(boys) + sum(girls)"
    Then the new metric appears in the metrics list

  Scenario: Delete a dataset column
    Given a column exists in the dataset
    When the user deletes that column
    Then the column no longer appears

  Scenario: Delete a dataset
    Given a temporary dataset has been created
    When the user deletes that dataset
    Then the dataset no longer appears in the list

  Scenario: Upload a CSV to create a dataset
    When the user uploads a local CSV file
    Then a new virtual dataset is created
    And the dataset content is queryable

  Scenario: Refresh dataset metadata
    Given a dataset exists
    When the user clicks "Refresh metadata"
    Then the metadata is reloaded

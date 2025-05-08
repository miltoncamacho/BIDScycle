# BIDScycle

This project is a BIDS compatible tool for easy renaming of BIDS data.

## Getting Started

To get started simply install using:

```bash
pip install bidscycle
```
or
```bash
pip install git+https://github.com/miltoncamacho/BIDScycle.git@main
```
for the bleading edge latest changes

## Usage

```bash
usage: bidscycle [-h] {create-duplicates,switch-duplicate,clean-duplicates}
```

You will need to select from the different commands to perform:

### create-duplicates

This command will help you create BIDS duplicates in any of the files that match the provided BIDS compatible filters.

```bash
usage: bidscycle create-duplicates [-h] -f entity=value[,value2] [--commit-msg COMMIT_MSG] [--dry-run] [--no-datalad] [-v] dataset
```

| Argument          | Description                                                                |
|-------------------|----------------------------------------------------------------------------|
| `dataset`         | Absolute path to the dataset containing `sub-XX` folders.                           |
| `--filter`,`-f`   | Entity filter in the format `entity=value[,value2]`.                       |
| `--commit-msg`    | Optional commit message for saving the changes.                            |
| `--dry-run`       | Perform a trial run without making any changes.                            |
| `--no-datalad`    | Skip Datalad commands during execution.                                    |
| `-v`              | Enable verbose output for debugging purposes.                              |

### switch-duplicates

```bash
usage: bidscycle switch-duplicates [-h] -f entity=value[,value2] [--commit-msg COMMIT_MSG] [--dry-run] [--no-datalad] [-v] dataset
```

| Argument          | Description                                                                |
|-------------------|----------------------------------------------------------------------------|
| `dataset`         | Absolute path to the dataset containing `sub-XX` folders.                  |
| `--filter`,`-f`   | Entity filter in the format `entity=value[,value2]` must contain dup.      |
| `--commit-msg`    | Optional commit message for saving the changes.                            |
| `--dry-run`       | Perform a trial run without making any changes.                            |
| `--no-datalad`    | Skip Datalad commands during execution.                                    |
| `-v`              | Enable verbose output for debugging purposes.                              |


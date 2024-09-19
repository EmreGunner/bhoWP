#!/bin/bash

# Set your Git commit message here
COMMIT_MESSAGE="Auto commit at $(date)"

# Check for changes, commit, and push every 5 minutes
while true
do
    # Move to the repository's root directory (optional)
    # cd /path/to/your/repository

    # Check for changes
    if ! git diff-index --quiet HEAD --; then
        echo "Changes detected. Committing and pushing changes..."
        
        # Add all changes to staging
        git add .

        # Commit with the default message
        git commit -m "$COMMIT_MESSAGE"

        # Push to the remote repository
        git push origin $(git rev-parse --abbrev-ref HEAD)
    else
        echo "No changes detected."
    fi

    # Wait for 5 minutes (300 seconds)
    sleep 300
done

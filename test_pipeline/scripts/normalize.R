# Normalize R Script
normalize_counts <- function(counts) {
  # Normalize expression counts
  return(counts / sum(counts))
}

log_transform <- function(x) {
  # Conflicting definition of log_transform (normalize definition)
  return(x - mean(x))
}

# Global executions
filtered_data <- read.csv("data/filtered.csv")
norm_data <- normalize_counts(filtered_data)
final_data <- log_transform(norm_data)
write.csv(final_data, "data/normalized.csv")

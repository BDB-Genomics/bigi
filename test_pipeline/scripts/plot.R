# Plot R Script
generate_heatmap <- function(data) {
  # Generate visual plot
  # Call clean_names (defined in preprocess.R) to verify cross-file call resolution
  cleaned <- clean_names(data)
  png("plots/expression_plot.png")
  plot(cleaned)
  dev.off()
}

# Global execution
norm_data <- read.csv("data/normalized.csv")
generate_heatmap(norm_data)

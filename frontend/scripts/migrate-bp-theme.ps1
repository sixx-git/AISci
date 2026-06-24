# One-off Blueprint color migration for tab page components (Phase B)
$root = Split-Path -Parent $PSScriptRoot
$files = @(
  'src/components/DatasetPage.tsx',
  'src/components/LiteratureLibrary.tsx',
  'src/components/ResearchQuestionPage.tsx',
  'src/components/KnowledgeGraphPage.tsx',
  'src/components/HypothesesPage.tsx',
  'src/components/ExperimentDesignPage.tsx',
  'src/components/ReportPage.tsx',
  'src/components/RunLogsPage.tsx',
  'src/components/AgentDetailPanel.tsx',
  'src/components/ResearchClosedLoopOverview.tsx',
  'src/components/PromptManagementPage.tsx',
  'src/components/DataFinderPanel.tsx',
  'src/components/MultimodalEvidencePanel.tsx',
  'src/components/DataCatalogPanel.tsx',
  'src/components/FeedbackHubPanel.tsx',
  'src/components/RunLogDetail.tsx',
  'src/components/RunLogTable.tsx',
  'src/components/HypothesisCard.tsx',
  'src/components/ClosedLoopTimeline.tsx',
  'src/components/WorkflowPage.tsx',
  'src/components/FederatedCampaignPanel.tsx',
  'src/components/StageHumanLoopPanel.tsx',
  'src/components/HitlGatePanel.tsx',
  'src/components/DiscoveryLoopPanel.tsx',
  'src/components/EvidenceChainDrawer.tsx',
  'src/components/HypothesisTreePanel.tsx',
  'src/components/HypothesisProvenanceTimeline.tsx',
  'src/components/ExternalCandidateTodoPanel.tsx',
  'src/components/FigureReviewPanel.tsx',
  'src/components/ReportChecklist.tsx',
  'src/components/QualityCheckCard.tsx',
  'src/components/VersionComparePanel.tsx',
  'src/components/EvidenceDiffPanel.tsx',
  'src/components/EnsembleReviewPanel.tsx',
  'src/components/IdeationNoveltyPanel.tsx',
  'src/components/PlotCritiquePanel.tsx',
  'src/components/PromptStageEditor.tsx',
  'src/components/PromptPresetBar.tsx',
  'src/components/MarkdownPreview.tsx'
)

$pairs = @(
  @('text-gray-500', 'text-bp-muted'),
  @('text-gray-400', 'text-bp-muted'),
  @('text-gray-300', 'text-bp-text'),
  @('text-gray-200', 'text-bp-text'),
  @('text-gray-600', 'text-bp-muted'),
  @('text-white', 'text-bp-text'),
  @('border-gray-700', 'border-bp-border'),
  @('border-gray-800', 'border-bp-border'),
  @('border-gray-600', 'border-bp-border'),
  @('border-dark-700', 'border-bp-border'),
  @('border-dark-600', 'border-bp-border'),
  @('bg-dark-900', 'bg-bp-base'),
  @('bg-dark-800', 'bg-bp-panel'),
  @('bg-gray-900', 'bg-bp-base'),
  @('bg-gray-800', 'bg-bp-panel'),
  @('bg-gray-700', 'bg-bp-surface'),
  @('border-primary-500', 'border-bp-cyan'),
  @('text-primary-500', 'text-bp-cyan'),
  @('text-primary-300', 'text-bp-cyan'),
  @('text-primary-400', 'text-bp-cyan'),
  @('bg-primary-500/10', 'bg-bp-cyan-tint'),
  @('bg-primary-600/20', 'bg-bp-cyan-tint'),
  @('hover:text-gray-300', 'hover:text-bp-text'),
  @('hover:text-primary-400', 'hover:text-bp-cyan'),
  @('hover:border-primary-600/50', 'hover:border-bp-cyan/40'),
  @('hover:border-primary-500/30', 'hover:border-bp-cyan/30'),
  @('focus:border-primary-500', 'focus:border-bp-cyan'),
  @('ring-primary-500', 'ring-bp-cyan'),
  @('ring-offset-dark-900', 'ring-offset-bp-base'),
  @('rounded-lg border border-gray-700', 'rounded-bp border border-bp-border'),
  @('placeholder-gray-500', 'placeholder:text-bp-muted'),
  @('placeholder:text-gray-600', 'placeholder:text-bp-muted')
)

foreach ($rel in $files) {
  $path = Join-Path $root $rel
  if (-not (Test-Path $path)) { continue }
  $content = [System.IO.File]::ReadAllText($path)
  $original = $content
  foreach ($pair in $pairs) {
    $content = $content.Replace($pair[0], $pair[1])
  }
  if ($content -ne $original) {
    [System.IO.File]::WriteAllText($path, $content)
    Write-Host "Updated $rel"
  }
}

Write-Host "=== Render Deployment Test ===" -ForegroundColor Cyan

$renderUrl = "https://franktech-backend.onrender.com"
Write-Host "Testing: $renderUrl" -ForegroundColor Yellow

# Test endpoints
$endpoints = @(
    "/api/health",
    "/api/mpesa/test", 
    "/api/games",
    "/"
)

foreach ($endpoint in $endpoints) {
    try {
        Write-Host "Testing $endpoint..." -NoNewline
        $response = Invoke-WebRequest -Uri "$renderUrl$endpoint" -TimeoutSec 10
        Write-Host " ✅ ($($response.StatusCode))" -ForegroundColor Green
    } catch {
        Write-Host " ❌ ($($_.Exception.Message))" -ForegroundColor Red
    }
}

Write-Host "`n=== Test Complete ===" -ForegroundColor Cyan

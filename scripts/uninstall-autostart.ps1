$task = Get-ScheduledTask -TaskName 'JarvisAutonomous' -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName 'JarvisAutonomous' -Confirm:$false
    Write-Output 'JarvisAutonomous startup task removed.'
} else {
    Write-Output 'JarvisAutonomous startup task is not installed.'
}

document.addEventListener('DOMContentLoaded', function () {
    // Check if there are any processing tasks
    const processingTasks = Array.from(document.querySelectorAll('td')).filter(td =>
        td.textContent.trim().toLowerCase().includes('processing')
    );

    if (processingTasks.length > 0) {
        console.log('Found processing tasks, enabling auto-refresh');
        // Refresh the page every 30 seconds
        setTimeout(function () {
            console.log('Auto-refreshing page');
            window.location.reload();
        }, 30000);
    } else {
        console.log('No processing tasks found');
    }
}); 
document.addEventListener('DOMContentLoaded', function () {
    // Find all the points input fields on the page
    const pointsInputs = document.querySelectorAll('.points-form input[type="number"]');

    pointsInputs.forEach(input => {
        input.addEventListener('input', function () {
            const form = this.closest('form');
            const action = form.querySelector('input[name="action"]').value;
            const pointsToChange = parseInt(this.value, 10) || 0;

            // Find the driver's current points and the preview element
            const currentRow = this.closest('tr');
            const currentPointsElement = currentRow.querySelector('.current-points');
            const previewElement = currentRow.querySelector('.points-preview');
            const currentPoints = parseInt(currentPointsElement.textContent, 10);

            let hypotheticalTotal;
            if (action === 'award') {
                hypotheticalTotal = currentPoints + pointsToChange;
            } else {
                hypotheticalTotal = currentPoints - pointsToChange;
            }

            // Display the preview
            if (pointsToChange > 0) {
                previewElement.textContent = `(New Total: ${hypotheticalTotal})`;
            } else {
                previewElement.textContent = ''; // Clear preview if input is empty
            }
        });
    });
});
/* Only synthetic content. Run through smoke.py; never targets an existing file. */
function createReviewFixture(destination) {
    var file = new File(destination), doc = null, result = "EXPORT_FAILED";
    if (file.exists) return "OUTPUT_EXISTS";
    if (app.userInteractionLevel !== UserInteractionLevel.DISPLAYALERTS) return "ALERTS_DISABLED";
    try {
        doc = app.documents.add(DocumentColorSpace.RGB, 300, 200);
        doc.artboards.add([320, 200, 620, 0]);
        for (var i = 0; i < 2; i++) {
            var rect = doc.pathItems.rectangle(180, 20 + i * 320, 180, 50);
            var red = new RGBColor(); red.red = 220; red.green = 20; red.blue = 40;
            rect.filled = true; rect.fillColor = red; rect.stroked = false;
            var text = doc.textFrames.add();
            text.contents = i === 0 ? "SYNTHETIC_ALPHA" : "SYNTHETIC_BETA";
            text.position = [20 + i * 320, 100];
            text.textRange.characterAttributes.size = 16;
        }
        var options = new IllustratorSaveOptions();
        options.pdfCompatible = false;
        doc.saveAs(file, options);
        result = "OK|2";
    } catch (error) { result = "EXPORT_FAILED"; }
    finally {
        if (doc !== null) {
            try { doc.close(SaveOptions.DONOTSAVECHANGES); }
            catch (closeError) { result = "CLOSE_FAILED"; }
        }
    }
    return result;
}

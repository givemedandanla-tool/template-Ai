/* Local, user-invoked Illustrator adapter. No preferences, originals or existing documents are saved. */
function reviewExport(request) {
    var doc = null, owned = false, result = "EXPORT_FAILED";
    function cancelled() { return new File(request.cancel).exists; }
    function key(file) { return file.fsName.replace(/\\/g, "/").toLowerCase(); }
    try {
        var source = new File(request.source), output = new File(request.output);
        if (!source.exists || !/\.ai$/i.test(source.name)) return "INVALID_SOURCE";
        if (key(source) === key(output) || output.exists) return "OUTPUT_EXISTS";
        if (cancelled()) return "CANCELLED";
        // Never hide missing font/link, colour-management or conversion warnings.
        if (app.userInteractionLevel !== UserInteractionLevel.DISPLAYALERTS) return "ALERTS_DISABLED";
        var before = [], i;
        for (i = 0; i < app.documents.length; i++) {
            before.push(app.documents[i]);
            try { if (key(app.documents[i].fullName) === key(source)) return "SOURCE_OPEN"; }
            catch (unsavedDocument) { /* Untitled document has no fullName. */ }
        }
        doc = app.open(source);
        // app.open can return an existing document (aliases, races). Do not touch it.
        for (i = 0; i < before.length; i++) if (doc === before[i]) return "SOURCE_OPEN";
        owned = true;
        if (cancelled()) return "CANCELLED";
        if (new File(request.output).exists) return "OUTPUT_EXISTS";
        var count = doc.artboards.length;
        if (count < 1 || count > 100) return "PAGE_LIMIT";
        var options = new PDFSaveOptions();
        options.compatibility = PDFCompatibility.ACROBAT6;
        options.artboardRange = ""; // All artboards, one PDF.
        options.preserveEditability = false;
        options.viewAfterSaving = false;
        options.requireDocumentPassword = false;
        options.requirePermissionPassword = false;
        doc.saveAs(output, options);
        result = cancelled() ? "CANCELLED" : "OK|" + count;
    } catch (error) {
        // Never return filenames, private text or raw Adobe exception messages.
        result = "EXPORT_FAILED";
    } finally {
        if (owned && doc !== null) {
            try { doc.close(SaveOptions.DONOTSAVECHANGES); }
            catch (closeError) { result = "CLOSE_FAILED"; }
        }
    }
    return result;
}

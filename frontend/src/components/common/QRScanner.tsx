import { useEffect, useRef, useState } from 'react';
import { Html5QrcodeScanner, Html5QrcodeSupportedFormats } from 'html5-qrcode';
import { X, Camera, AlertCircle } from 'lucide-react';

interface QRScannerProps {
    onScan: (decodedText: string) => void;
    onClose: () => void;
}

const QRScanner = ({ onScan, onClose }: QRScannerProps) => {
    const scannerRef = useRef<Html5QrcodeScanner | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        // Initialize Scanner
        // Use a unique ID for the element
        const elementId = "qr-reader";

        // Config
        const config = {
            fps: 10,
            qrbox: { width: 250, height: 250 },
            formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE],
            verbose: false
        };

        try {
            scannerRef.current = new Html5QrcodeScanner(elementId, config, false);

            scannerRef.current.render(
                (decodedText) => {
                    // Success callback
                    onScan(decodedText);
                    // Stop scanning after success to prevent multiple triggers
                    if (scannerRef.current) {
                        try {
                            scannerRef.current.clear();
                        } catch (e) {
                            console.error("Failed to clear scanner", e);
                        }
                    }
                },
                (errorMessage) => {
                    // Error callback (called constantly when no QR found, ignore mostly)
                    // console.log(errorMessage);
                }
            );
        } catch (err) {
            console.error("Failed to initialize scanner", err);
            setError("Kamera konnte nicht gestartet werden. Bitte Berechtigungen prüfen.");
        }

        return () => {
            if (scannerRef.current) {
                try {
                    scannerRef.current.clear();
                } catch (e) {
                    console.error("Failed to clear scanner on unmount", e);
                }
            }
        };
    }, [onScan]);

    return (
        <div className="fixed inset-0 z-[60] bg-black/80 flex items-center justify-center p-4">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-md overflow-hidden relative">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b">
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                        <Camera className="w-5 h-5 text-minga-600" />
                        Code Scannen
                    </h3>
                    <button
                        onClick={onClose}
                        className="p-1 hover:bg-gray-100 rounded-full transition-colors"
                    >
                        <X className="w-6 h-6 text-gray-500" />
                    </button>
                </div>

                {/* Scanner Area */}
                <div className="p-4 bg-gray-50 min-h-[300px] flex flex-col items-center justify-center">
                    {error ? (
                        <div className="text-center text-red-500">
                            <AlertCircle className="w-12 h-12 mx-auto mb-2" />
                            <p>{error}</p>
                        </div>
                    ) : (
                        <div id="qr-reader" className="w-full"></div>
                    )}
                    <p className="text-sm text-gray-500 mt-4 text-center">
                        Richten Sie die Kamera auf einen QR-Code auf dem Etikett.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default QRScanner;

import { Modal } from '../ui/Modal';
import { Button } from '../ui';
import { AttachmentsPanel } from './AttachmentsPanel';
import { AttachmentEntityType } from '../../services/api';

interface Props {
  open: boolean;
  onClose: () => void;
  entityType: AttachmentEntityType;
  entityId: string | null;
  entityName: string;
  defaultCertificateType?: string;
}

export function AttachmentsModal({ open, onClose, entityType, entityId, entityName, defaultCertificateType }: Props) {
  return (
    <Modal
      open={open && !!entityId}
      onClose={onClose}
      title={`Anhänge — ${entityName}`}
      size="lg"
      footer={<Button variant="secondary" onClick={onClose}>Schließen</Button>}
    >
      {entityId && (
        <AttachmentsPanel
          entityType={entityType}
          entityId={entityId}
          defaultCertificateType={defaultCertificateType}
        />
      )}
    </Modal>
  );
}

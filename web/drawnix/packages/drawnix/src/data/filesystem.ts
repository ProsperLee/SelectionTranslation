import type { FileSystemHandle as BrowserFileSystemHandle } from 'browser-fs-access';
import {
  fileOpen as _fileOpen,
  fileSave as _fileSave,
  supported as nativeFileSystemSupported,
} from 'browser-fs-access';
import { MIME_TYPES } from '../constants';
import { blobToDataUrl, getDrawnixHost } from '../utils/common';

type FILE_EXTENSION = Exclude<keyof typeof MIME_TYPES, 'binary'>;

export type FileSystemHandle = BrowserFileSystemHandle | FileSystemFileHandle;

type HostOpenResult = {
  name: string;
  mime: string;
  base64: string;
};

const fileFromHostResult = (raw: string): File => {
  const parsed = JSON.parse(raw) as HostOpenResult;
  const binary = atob(parsed.base64 || '');
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new File([bytes], parsed.name || 'file', {
    type: parsed.mime || 'application/octet-stream',
  });
};

export const fileOpen = <M extends boolean | undefined = false>(opts: {
  extensions?: FILE_EXTENSION[];
  description: string;
  multiple?: M;
}): Promise<M extends false | undefined ? File : File[]> => {
  // an unsafe TS hack, alas not much we can do AFAIK
  type RetType = M extends false | undefined ? File : File[];

  const host = getDrawnixHost();
  if (host?.openFile && !opts.multiple) {
    return host
      .openFile(
        JSON.stringify({
          description: opts.description,
          extensions: opts.extensions || [],
          multiple: false,
        })
      )
      .then((raw) => {
        if (!raw) {
          return Promise.reject(new DOMException('The user aborted a request.', 'AbortError'));
        }
        return fileFromHostResult(raw) as RetType;
      });
  }

  const mimeTypes = opts.extensions?.reduce((mimeTypes, type) => {
    mimeTypes.push(MIME_TYPES[type]);

    return mimeTypes;
  }, [] as string[]);

  const extensions = opts.extensions?.reduce((acc, ext) => {
    if (ext === 'jpg') {
      return acc.concat('.jpg', '.jpeg');
    }
    return acc.concat(`.${ext}`);
  }, [] as string[]);

  return _fileOpen({
    description: opts.description,
    extensions,
    mimeTypes,
    multiple: opts.multiple ?? false,
  }) as Promise<RetType>;
};

export const fileSave = (
  blob: Blob | Promise<Blob>,
  opts: {
    /** supply without the extension */
    name: string;
    /** file extension */
    extension: FILE_EXTENSION;
    description: string;
    /** existing FileSystemHandle */
    fileHandle?: FileSystemHandle | null;
  }
) => {
  const host = getDrawnixHost();
  if (host?.saveBlob) {
    return Promise.resolve(blob).then(async (resolved) => {
      const dataUrl = await blobToDataUrl(resolved);
      host.saveBlob(
        dataUrl,
        `${opts.name}.${opts.extension}`,
        resolved.type || 'application/octet-stream'
      );
      return null;
    });
  }

  return _fileSave(
    blob,
    {
      fileName: `${opts.name}.${opts.extension}`,
      description: opts.description,
      extensions: [`.${opts.extension}`],
    },
    opts.fileHandle as any
  );
};

export { nativeFileSystemSupported };

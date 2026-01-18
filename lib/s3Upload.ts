import { S3Client } from '@aws-sdk/client-s3';
import { Upload } from '@aws-sdk/lib-storage';
import { Readable } from 'stream';

const s3 = new S3Client({
  region: process.env.AWS_REGION!,
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
  },
});

interface UploadStreamParams {
  stream: Readable;
  fileName: string;
  contentType: string;
}

export async function uploadStreamToS3({
  stream,
  fileName,
  contentType,
}: UploadStreamParams): Promise<string> {
  const upload = new Upload({
    client: s3,
    params: {
      Bucket: process.env.AWS_S3_BUCKET!,
      Key: `images/${Date.now()}-${fileName}`,
      Body: stream,
      ContentType: contentType,
    },
  });

  const result = await upload.done();

  if (!result.Location) {
    throw new Error('S3 업로드 실패: Location 없음');
  }

  return result.Location;
}

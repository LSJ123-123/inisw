import { NextRequest, NextResponse } from 'next/server';
import { MongoClient } from 'mongodb';
import AWS from 'aws-sdk';

export async function GET(req: NextRequest) {
  const {
    MONGODB_URI,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_S3_BUCKET_NAME,
    AWS_S3_REGION
  } = process.env;

  if (!MONGODB_URI || !AWS_ACCESS_KEY_ID || !AWS_SECRET_ACCESS_KEY || !AWS_S3_BUCKET_NAME || !AWS_S3_REGION) {
    return NextResponse.json({ message: 'Missing environment variables' }, { status: 500 });
  }

  // AWS S3 config
  AWS.config.update({
    accessKeyId: AWS_ACCESS_KEY_ID,
    secretAccessKey: AWS_SECRET_ACCESS_KEY,
    region: AWS_S3_REGION,
  });

  const s3 = new AWS.S3();
  const client = new MongoClient(MONGODB_URI);

  try {
    await client.connect();
    const db = client.db('yourDatabaseName'); // DB 이름 수정 필요
    const images = await db.collection('images').find().toArray();

    const imageData = await Promise.all(images.map(async image => {
      const maskImages = image.mask_images.map((mask: any) => ({
        url: mask[`mask_img_${mask.cluster_id.$numberInt}`],
        clusterCenter: {
          x: mask.cluster_center.x.$numberDouble,
          y: mask.cluster_center.y.$numberDouble
        },
        clusterId: mask.cluster_id.$numberInt
      }));

      return {
        ...image,
        s3Url: image.s3_url,
        maskImages
      };
    }));

    return NextResponse.json(imageData);
  } catch (error) {
    console.error('Failed to retrieve data', error);
    return NextResponse.json({ message: 'Failed to retrieve data' }, { status: 500 });
  } finally {
    await client.close();
  }
}

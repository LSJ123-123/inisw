import { NextRequest, NextResponse } from 'next/server';
import { uploadFileToS3 } from '@/lib/s3Upload';
import { saveImageToDB, findImageByName } from '@/lib/saveImageToDB';

export async function POST(req: NextRequest) {
  try {
    const data = await req.formData();
    const file = data.get('file') as File;

    if (!file) {
      return NextResponse.json({ error: '파일이 없습니다.' }, { status: 400 });
    }

    // DB에서 동일한 이름 파일 조회
    let existingImage;
    try {
      existingImage = await findImageByName(file.name);
    } catch (dbErr) {
      console.error('DB 조회 실패:', dbErr);
      return NextResponse.json(
        { error: 'DB 조회 중 오류 발생', details: dbErr instanceof Error ? dbErr.message : 'Unknown error' },
        { status: 500 }
      );
    }

    if (existingImage) {
      return NextResponse.json({ message: '이미 업로드된 파일입니다.', image: existingImage }, { status: 200 });
    }

    // Buffer 변환
    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // S3 업로드
    let s3Url;
    try {
      s3Url = await uploadFileToS3({
        buffer,
        originalname: file.name,
        mimetype: file.type,
      });
    } catch (s3Err) {
      console.error('S3 업로드 실패:', s3Err);
      return NextResponse.json(
        { error: 'S3 업로드 중 오류 발생', details: s3Err instanceof Error ? s3Err.message : 'Unknown error' },
        { status: 500 }
      );
    }

    // DB 저장
    let savedImage;
    try {
      savedImage = await saveImageToDB({
        image_name: file.name,
        s3_url: s3Url,
      });
    } catch (dbSaveErr) {
      console.error('DB 저장 실패:', dbSaveErr);
      return NextResponse.json(
        { error: 'DB 저장 중 오류 발생', details: dbSaveErr instanceof Error ? dbSaveErr.message : 'Unknown error' },
        { status: 500 }
      );
    }

    return NextResponse.json({ message: '이미지 업로드 성공', image: savedImage }, { status: 200 });

  } catch (err) {
    console.error('예상치 못한 서버 오류:', err);
    const message = err instanceof Error ? err.stack || err.message : 'Unknown error';
    return NextResponse.json({ error: '서버 처리 중 오류 발생', details: message }, { status: 500 });
  }
}

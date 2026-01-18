export const runtime = 'nodejs';

import { NextRequest, NextResponse } from 'next/server';
import { Readable } from 'stream';
import { uploadStreamToS3 } from '@/lib/s3Upload';
import { saveImageToDB, findImageByName } from '@/lib/saveImageToDB';

export async function POST(req: NextRequest) {
  try {
    // 1. 요청 데이터 확인
    const formData = await req.formData();
    const file = formData.get('file') as File | null;

    if (!file) {
      return NextResponse.json({ error: '파일이 없습니다.' }, { status: 400 });
    }

    // 2. 중복 이미지 체크
    const existingImage = await findImageByName(file.name);
    if (existingImage) {
      return NextResponse.json(
        { message: '이미 업로드된 파일입니다.', image: existingImage },
        { status: 200 }
      );
    }

    // 3. 파일을 Buffer로 변환 (Reader보다 안정적인 방식)
    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // 4. S3 업로드 (Node Stream으로 변환하여 전달)
    // uploadStreamToS3 함수가 Readable 스트림을 받으므로 Readable.from을 사용합니다.
    const s3Url = await uploadStreamToS3({
      stream: Readable.from(buffer),
      fileName: file.name,
      contentType: file.type,
    });

    // 5. DB 저장
    const savedImage = await saveImageToDB({
      image_name: file.name,
      s3_url: s3Url,
    });

    return NextResponse.json(
      { message: '이미지 업로드 성공', image: savedImage },
      { status: 200 }
    );
  } catch (err) {
    // 서버 터미널에 상세 에러 출력 (디버깅용)
    console.error('--- 서버 업로드 상세 오류 시작 ---');
    console.error(err);
    console.error('--- 서버 업로드 상세 오류 끝 ---');

    return NextResponse.json(
      {
        error: '서버 처리 중 오류 발생',
        details: err instanceof Error ? err.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}